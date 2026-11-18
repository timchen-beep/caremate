# -*- coding: utf-8 -*-
# 作用：逐分支静态体检：乱码/缺作用头/语法错/过期数字/写死令牌/失效链接/文件被截断，输出清单供逐条修
"""分支体检工具（只读）。

为什么需要：九条分支各存一份代码与文档，main 改完只保证 main 对；
分支上的 README、页面说明、文档数字很容易停在旧状态（"九套/21 项"、"app-elder-001"、
`home/terminal/ack`）。手工逐分支翻 160 个文件不现实，所以先用脚本把"确定有问题"的捞出来。

用法：

    python tools/audit_branches.py                # 全部九条分支
    python tools/audit_branches.py --branch web   # 只看一条
    python tools/audit_branches.py --json out.json

判定口径（都是可机械判定的，不含主观意见）：

1. 乱码：出现 `锟` `�` `鏁` `鍙` `锛` 之类；文件头有 BOM。
2. 缺「作用」头：.py/.md/.html/.js/.qml 前三行里没有 `作用：`（配置、资源、许可证除外）。
3. 语法：`.py` 用 `compile()` 过一遍（不执行）。
4. 数字漂移：文档里写「N 套验收」，与该分支实际 `test_*.py` 套数不符。
5. 写死令牌：.html 里出现 `value="app-elder-001"` / `fam-demo-2026` / `comm-demo-2026` / `8823`。
6. 失效 topic：`home/terminal/ack` 只在 topics/硬件文档里算"预留"，别处出现就是过期。
7. 失效链接：相对链接指向的文件在该分支里不存在。
8. 截断：与 main 同路径文件比，分支文件不到 main 的一半且 main 超过 2 KB。
"""
import argparse
import json
import os
import re
import subprocess
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRANCHES = ["main", "web", "qt", "v1-web", "v1-web-core", "v2-qt", "v2-qt-core",
            "v3-flash", "v3-flash-core"]
TEXT_EXT = (".py", ".md", ".html", ".js", ".qml", ".cpp", ".h", ".json", ".yml",
            ".yaml", ".sh", ".ino", ".txt", ".webmanifest", ".vbs", ".bat", ".css",
            ".example", ".service", ".conf", ".gitignore", ".desktop", ".pro")
NEED_HEADER = (".py", ".md", ".html", ".js", ".qml")
NO_HEADER_OK = ("LICENSE", "requirements.txt", ".gitignore", ".env.example",
                "manifest.webmanifest", "package.json", "tsconfig.json")
MOJI = ("锟", "\ufffd", "鏁", "鍙", "锛", "涓", "鐨")
HTML_BAD_TOKEN = re.compile(
    r'value\s*=\s*"(app-elder-001|fam-demo-2026|comm-demo-2026|8823)"'
    r'|\|\|\s*"(app-elder-001|fam-demo-2026|comm-demo-2026)"')
SUITE_RE = re.compile(r"([一二三四五六七八九十]|\d+)\s*套\s*(?:验收|回归|自测)")
DEV_SCRIPTS = ("test_auto_scheduler.py",)  # 开发用的手验脚本，不算验收套件
CN = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8,
      "九": 9, "十": 10}
LINK_RE = re.compile(r"\]\(([^)\s]+)\)")
TOPIC_OK = ("topics.md", "硬件接入.md", "HARDWARE.md", "bridge.py", "README.md")


def git(*args):
    return subprocess.run(["git", "-c", "core.quotepath=false"] + list(args),
                          cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def files_of(branch):
    out = git("ls-tree", "-r", "--name-only", branch)
    if out.returncode != 0:
        raise SystemExit("读不到分支 %s：%s" % (branch, out.stderr.strip()))
    return [p for p in out.stdout.splitlines() if p]


def show(branch, path):
    out = git("show", "%s:%s" % (branch, path))
    return out.stdout if out.returncode == 0 else ""


def is_text(path):
    low = path.lower()
    return low.endswith(TEXT_EXT) or "/.gitignore" in low


def in_history_section(body, pos):
    """判断 pos 是否落在「版本变更/历史」小节里：那里写的是当时的事实，改了就是篡改历史。"""
    head = body[:pos]
    idx = head.rfind("\n## ")
    if idx < 0:
        return False
    line = head[idx:].split("\n", 2)[1] if "\n" in head[idx:] else head[idx:]
    return line.startswith("## v") or "历史" in line or "变更" in line or "版本" in line


def audit(branch):
    paths = files_of(branch)
    suites = [p for p in paths
              if re.search(r"test_\w+\.py$", p)
              and os.path.basename(p) not in DEV_SCRIPTS]
    suite_count = len(suites)
    main_paths = set(files_of("main")) if branch != "main" else set(paths)
    issues = []
    for path in paths:
        if not is_text(path):
            continue
        body = show(branch, path)
        if not body:
            continue
        head = "\n".join(body.splitlines()[:3])

        # 本文件把待查的字面量写在模式里，会把自己查出来，跳过
        if path.endswith("tools/audit_branches.py"):
            continue

        for bad in MOJI:
            if bad in body:
                issues.append((path, "乱码", "含 %r（编码坏了）" % bad))
                break
        if body.startswith("\ufeff"):
            issues.append((path, "BOM", "文件头有 BOM，Python 会报 Illegal character"))

        name = os.path.basename(path)
        if path.endswith(NEED_HEADER) and name not in NO_HEADER_OK and "作用：" not in head:
            issues.append((path, "缺作用头", "前三行没有「作用：」"))

        if path.endswith(".py"):
            try:
                compile(body, path, "exec")
            except SyntaxError as exc:
                issues.append((path, "语法错误", "%s: %s" % (exc.lineno, exc.msg)))

        if path.endswith(".md"):
            # 索引/汇总类文件是生成物或历史记录，里面的套数是"当时跑了多少"，不参与现状比对
            snap = (os.path.basename(path) in ("FILES.md", "FUNCTIONS.md", "MANIFEST.md")
                    or "evidence" in path or "汇总" in path)
            if not snap:
                for m in SUITE_RE.finditer(body):
                    if in_history_section(body, m.start()):
                        continue
                    raw = m.group(1)
                    num = int(raw) if raw.isdigit() else CN.get(raw, -1)
                    start = body.rfind("\n", 0, m.start()) + 1
                    end = body.find("\n", m.start())
                    line = body[start:end if end > 0 else len(body)]
                    # 讲别的分支有几套、或已经加了"未纳入汇总"的限定，都不算漂移
                    quoted = ("分支" in line or "未纳入" in line or "另有" in line)
                    if num > 0 and num != suite_count and not quoted:
                        issues.append((path, "数字漂移",
                                       "写「%s 套」，本分支实际 %d 套" % (raw, suite_count)))
                        break

        if path.endswith(".html"):
            m = HTML_BAD_TOKEN.search(body)
            if m:
                issues.append((path, "写死令牌", "命中 %r" % (m.group(0)[:40],)))

        if "home/terminal/ack" in body and not any(k in path for k in TOPIC_OK):
            # 注释里提到它多半是在解释"某个旧 bug"，不是真的在用这个 topic
            live = [ln for ln in body.splitlines()
                    if "home/terminal/ack" in ln and not ln.strip().startswith("#")]
            if live:
                issues.append((path, "失效 topic", "home/terminal/ack 已不在约定里"))

        if path.endswith(".md"):
            base = os.path.dirname(path)
            for m in LINK_RE.finditer(body):
                link = m.group(1)
                if link.startswith(("http://", "https://", "mailto:", "#", "<")):
                    continue
                target = urllib.parse.unquote(link.split("#")[0])
                if not target:
                    continue
                rel = os.path.normpath(os.path.join(base, target.replace("/", os.sep)))
                rel = rel.replace(os.sep, "/")
                if not any(p == rel or p.startswith(rel.rstrip("/") + "/") for p in paths):
                    issues.append((path, "失效链接", link))

        if branch != "main" and path in main_paths and path.endswith(".py"):
            # 只看代码：分支上的 .md 本来就更短（只讲本分支那一条路线），不是被截断
            size = len(body.encode("utf-8"))
            main_size = len(show("main", path).encode("utf-8"))
            if main_size > 2048 and size * 2 < main_size:
                issues.append((path, "疑似截断", "%d B，main 是 %d B" % (size, main_size)))
    return {"branch": branch, "files": len(paths), "suites": suite_count,
            "issues": [{"path": p, "kind": k, "detail": d} for p, k, d in issues]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--branch", default="")
    ap.add_argument("--json", default="")
    args = ap.parse_args()
    branches = [args.branch] if args.branch else BRANCHES
    report = []
    total = 0
    for b in branches:
        r = audit(b)
        report.append(r)
        total += len(r["issues"])
        print("=== %s：%d 个文件，%d 套验收，%d 处问题" % (b, r["files"], r["suites"],
                                                       len(r["issues"])))
        for it in r["issues"][:60]:
            print("   [%s] %s —— %s" % (it["kind"], it["path"], it["detail"]))
        if len(r["issues"]) > 60:
            print("   … 还有 %d 处" % (len(r["issues"]) - 60))
    print("\n合计 %d 处问题" % total)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=1)
        print("清单已写入 %s" % args.json)
    return 0 if total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
