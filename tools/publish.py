# -*- coding: utf-8 -*-
# 作用：一条命令发布：先全量验证，再逐文件提交（说明取自文件自己的「作用」注释），最后推送并等 CI
"""把"改完 → 验证 → 提交 → 推送"压成一条命令。

用法：

    python tools/publish.py              # 验证 + 逐文件提交 + 推送
    python tools/publish.py --dry-run    # 只打印将要提交什么
    python tools/publish.py --no-verify  # 跳过验证（不建议，仅救急）
    python tools/publish.py --branch web   # 指定分支（默认：当前分支）

规则（与 CONTRIBUTING.md 一致）：

1. **验证不过不提交**：`verify_all.py` 失败就直接退出，一个文件都不提交。
2. **一个文件一个提交**：提交信息是 `<路径>：<该文件「作用」注释>`，方便回溯"这个文件为什么存在"。
3. **目录也能提交**：`git status` 里的 `?? dir/` 会被展开成目录下的每个文件
   ——之前就是因为只处理 `isfile`，`qt/net/` 四个文件漏提交，远端仓库缺文件。
4. **推送重试三次**：网络抖动时不至于半途而废。
"""

import argparse
import io
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESC_PAT = re.compile(r"作用[：:]\s*(.+?)\s*(?:-->|--)?\s*$", re.M)
BINARY_EXT = {".png", ".jpg", ".jpeg", ".jar", ".apk", ".aab", ".ico", ".db", ".zip",
              ".docx", ".xlsx", ".pptx", ".keystore", ".patch"}


def run(args, cwd=None, capture=True):
    return subprocess.run(args, cwd=cwd or ROOT, capture_output=capture, text=True,
                          encoding="utf-8", errors="replace")


def git(*args):
    return run(["git", "-C", ROOT, "-c", "core.quotepath=false"] + list(args))


def changed_paths():
    """把 git status 的路径展开成"文件级"列表（目录递归展开）。"""
    out = git("status", "--porcelain").stdout.splitlines()
    files = []
    for line in out:
        rel = line[3:].strip().strip('"')
        full = os.path.join(ROOT, rel.replace("/", os.sep))
        if os.path.isdir(full):
            for dirpath, _dirs, names in os.walk(full):
                for name in names:
                    files.append(os.path.relpath(os.path.join(dirpath, name), ROOT).replace(os.sep, "/"))
        elif os.path.isfile(full):
            files.append(rel)
        else:
            files.append(rel)   # 删除的文件：交给 git add -A
    return sorted(set(files))


def describe(rel):
    full = os.path.join(ROOT, rel.replace("/", os.sep))
    ext = os.path.splitext(rel)[1].lower()
    if ext in BINARY_EXT:
        return "二进制资源"
    try:
        head = io.open(full, encoding="utf-8", errors="replace").read(4000)
    except OSError:
        return "删除的文件"
    match = DESC_PAT.search(head)
    if match:
        return match.group(1).strip()
    if ext == ".md":
        first = head.split("\n", 1)[0].lstrip("# ").strip()
        if first:
            return first[:60]
    return "改动"


def commit_one(rel):
    msg = "%s：%s" % (rel, describe(rel))
    if len(msg) > 115:
        msg = msg[:112] + "..."
    git("add", "-A", "--", rel)
    return git("commit", "-q", "-m", msg, "--", rel)


def main():
    ap = argparse.ArgumentParser(description="验证 → 逐文件提交 → 推送")
    ap.add_argument("--dry-run", action="store_true", help="只打印，不提交不推送")
    ap.add_argument("--no-verify", action="store_true", help="跳过全量验证（不建议）")
    ap.add_argument("--branch", default="",
                    help="推送的分支；默认是当前所在分支（避免在 web/qt 分支上误推 main）")
    args = ap.parse_args()

    if not args.branch:
        args.branch = git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip() or "main"
        if args.branch in ("HEAD", "(no branch)"):
            print("当前是游离 HEAD，请用 --branch 指定分支。")
            return 1
        print("当前分支：%s（要推别的分支用 --branch）" % args.branch)

    files = changed_paths()
    if not files:
        print("没有改动，工作区是干净的。")
        return 0
    print("待提交 %d 个文件：" % len(files))
    for rel in files:
        print("  - %s（%s）" % (rel, describe(rel)))

    if args.dry_run:
        print("\n[dry-run] 未验证、未提交、未推送。")
        return 0

    if not args.no_verify:
        print("\n=== 1/3 全量验证 ===")
        proc = run([sys.executable, os.path.join(ROOT, "tools", "verify_all.py")],
                   cwd=os.path.join(ROOT, "server") if False else ROOT, capture=False)
        if proc.returncode != 0:
            print("\n验证未通过：一个文件都没提交。先修到全绿再发。")
            return 1
        print("验证通过。")

    print("\n=== 2/3 逐文件提交 ===")
    committed = 0
    failed = []
    for rel in files:
        result = commit_one(rel)
        if result.returncode == 0:
            committed += 1
            print("  已提交 %s" % rel)
        elif "nothing to commit" in (result.stdout + result.stderr):
            print("  跳过 %s（无内容变化）" % rel)
        else:
            failed.append(rel)
            print("  失败 %s：%s" % (rel, (result.stderr or "").strip()[:120]))
    print("共提交 %d 个文件。" % committed)
    if failed:
        # 有文件没提交进去就不推送：否则推上去的是半套改动，别人拉下来会缺文件。
        print("\n有 %d 个文件提交失败：%s" % (len(failed), ", ".join(failed)))
        print("已中止推送（剩下的改动还在工作区，修好重跑本命令即可）。")
        return 1

    print("\n=== 3/3 推送 origin/%s ===" % args.branch)
    from push_helper import push as smart_push
    ok, message = smart_push(args.branch, ROOT)
    print(message)
    if ok:
        head = git("rev-parse", "--short", "HEAD").stdout.strip()
        print("HEAD=%s；CI 会自动跑同一条验证命令：" % head)
        print("  https://github.com/timchen-beep/caremate/actions")
        return 0
    print("改动已提交，但没有推上去（工作区是干净的，重跑本命令会继续推送）。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
