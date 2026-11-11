# -*- coding: utf-8 -*-
# 作用：按"分支迭代、main 定期合并"的流程，把 web / qt 分支的成果合并回 main（按归属路径拉取，验证后提交推送）
"""main 从迭代分支合并的工具。

流程（方案 2）：

    改网页端 → 在 web 分支迭代（python tools/publish.py，自动推 web）
    改 Qt 端 → 在 qt 分支迭代
    定期    → 回 main 跑 python tools/merge_from_branches.py，把两个分支的成果合回 main

为什么不用 `git merge`：web / qt 是 orphan 分支（和 main 没有共同历史），整枝合并会带来
"把分支独有文件当新增"和大量伪冲突。这里改为**按归属路径拉取**：

    web → server/ 、 tools/ 、 docs/ 、 README.md（网页端自己维护的那些）
    qt  → qt/ 、 integration/

`git checkout <branch> -- <path>` 只会覆盖/新增分支里存在的文件，**不会删除** main 上
分支没有的文件（例如 main 的 Flutter 与硬件目录不会被清掉）。

用法：

    python tools/merge_from_branches.py --dry-run     # 看会拉哪些文件
    python tools/merge_from_branches.py               # 拉取 → 验证 → 逐文件提交 → 推送 main
    python tools/merge_from_branches.py --no-verify   # 跳过验证（不建议）
"""

import argparse
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 归属：这些目录整体跟随分支（分支里没有的文件会被删掉，所以只放"分支也全有"的目录）
OWNER_DIRS = {
    "web": ["server"],
    "qt": ["qt", "integration"],
}
# 文档：只更新"main 与分支都存在"的文件，绝不删除 main 独有的文档
DOC_DIR = "docs"


def git(*args, cwd=None):
    return subprocess.run(["git", "-C", cwd or ROOT, "-c", "core.quotepath=false"] + list(args),
                          capture_output=True, text=True, encoding="utf-8", errors="replace")


def changed_paths():
    out = git("status", "--porcelain").stdout.splitlines()
    return [line[3:].strip().strip('"') for line in out]


def describe(rel):
    import io
    import re
    path = os.path.join(ROOT, rel.replace("/", os.sep))
    if not os.path.isfile(path):
        return "移除（分支里已不存在）"
    try:
        head = io.open(path, encoding="utf-8", errors="replace").read(4000)
    except OSError:
        return "二进制资源"
    match = re.search(r"作用[：:]\s*(.+?)\s*(?:-->|--)?\s*$", head, re.M)
    if match:
        return match.group(1).strip()
    if rel.endswith(".md"):
        first = head.split("\n", 1)[0].lstrip("# ").strip()
        if first:
            return first[:60]
    return "合并自迭代分支"


def main():
    ap = argparse.ArgumentParser(description="把 web / qt 分支的成果合回 main")
    ap.add_argument("--dry-run", action="store_true", help="只看会拉哪些文件")
    ap.add_argument("--no-verify", action="store_true", help="跳过全量验证（不建议）")
    ap.add_argument("--branch", default="main", help="合并到哪个分支（默认 main）")
    args = ap.parse_args()

    git("fetch", "origin", "-q")
    current = git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if current != args.branch:
        print("当前在 %s，请先切到 %s 再合并（避免在迭代分支上把另一个分支拉进来）。"
              % (current, args.branch))
        return 1

    # main 的 docs 里哪些文件在分支上也存在（只有这些会被更新）
    main_docs = [l for l in git("ls-tree", "-r", "--name-only", "HEAD", DOC_DIR).stdout.splitlines() if l]
    pulled = 0
    for branch, dirs in OWNER_DIRS.items():
        ref = "origin/%s" % branch
        exists = git("rev-parse", "--verify", ref).returncode == 0
        if not exists:
            print("跳过 %s（远端没有这个分支）" % branch)
            continue
        common_docs = [rel for rel in main_docs
                       if git("cat-file", "-e", "%s:%s" % (ref, rel)).returncode == 0]
        paths = list(dirs) + common_docs
        print("\n=== 从 %s 拉取：%s（文档 %d 个）==="
              % (branch, ", ".join(dirs), len(common_docs)))
        result = git("checkout", ref, "--", *paths)
        if result.returncode != 0:
            print("  拉取失败：%s" % (result.stderr or "").strip()[:160])
            continue
        pulled += 1
        for rel in changed_paths():
            print("  %s" % rel)

    files = changed_paths()
    if not files:
        print("\nmain 已经是最新：两个迭代分支没有新变化。")
        return 0
    print("\n共 %d 个文件有变化。" % len(files))
    if args.dry_run:
        print("[dry-run] 未验证、未提交、未推送。")
        return 0

    if not args.no_verify:
        print("\n=== 验证 ===")
        proc = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "verify_all.py")],
                              cwd=ROOT)
        if proc.returncode != 0:
            print("验证未通过：已拉取但未提交。修好再合并，或 git checkout -- . 放弃本次合并。")
            return 1
        print("验证通过。")

    print("\n=== 逐文件提交 ===")
    committed = 0
    for rel in files:
        msg = "%s：%s" % (rel, describe(rel))
        if len(msg) > 115:
            msg = msg[:112] + "..."
        git("add", "-A", "--", rel)
        if git("commit", "-q", "-m", msg, "--", rel).returncode == 0:
            committed += 1
            print("  已提交 %s" % rel)
    print("提交 %d 个文件。" % committed)

    print("\n=== 推送 origin/%s ===" % args.branch)
    from push_helper import push as smart_push
    ok, message = smart_push(args.branch, ROOT)
    print(message)
    if ok:
        print("HEAD=%s" % git("rev-parse", "--short", "HEAD").stdout.strip())
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
