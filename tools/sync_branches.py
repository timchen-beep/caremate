# -*- coding: utf-8 -*-
# 作用：一条命令把 main 的服务端核心同步到六条归档分支：差异核对 → 覆盖 → 起服务验证 → 逐文件提交 → 推送
"""分支同步工具。

背景：六条归档分支（v1-web / v1-web-core / v2-qt / v2-qt-core / v3-flash / v3-flash-core）
各自带着一份 `server.py`。main 每次改服务端（三档升级链、端云同步、`/v1` 适配），
都要把这几份补齐——手工做容易漏，也容易把 `caremate.db` 之类的东西带进去。

用法：

    python tools/sync_branches.py --dry-run        # 只看哪些分支需要同步
    python tools/sync_branches.py                  # 同步 + 验证 + 提交 + 推送
    python tools/sync_branches.py --only v1-web,v2-qt
    python tools/sync_branches.py --keep           # 保留 worktree 便于检查

同步的文件（main → 分支同目录）：

    server/server.py       → <分支>/caremate-cloud/server.py 或 legacy-web/server.py
    server/v1_adapter.py   → 同上
    server/test_v1.py      → 同上
    docs/客户端框架说明.md  → docs/ 或分支根目录

验证（每个有改动的分支）：

    1. py_compile 三个文件
    2. test_accept.py（自带服务与重启用例）
    3. 起服务（临时库）→ test_v1.py（9 项契约）
    4. 清理测试产物（caremate.db / acceptance.json / __pycache__），确保不混进提交
"""

import argparse
import io
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRANCHES = ["v1-web", "v1-web-core", "v2-qt", "v2-qt-core", "v3-flash", "v3-flash-core",
            "web", "qt"]
# 迭代分支（web/qt）的 server/ 在仓库根，归档分支在 caremate-cloud/ 或 legacy-web/ 下
ITER_BRANCHES = {"web", "qt"}
TOOL_FILES = ["tools/verify_all.py", "tools/publish.py", "tools/gen_index.py",
              "tools/sample_p95.py", "tools/collect_evidence.py", "tools/README.md"]
SYNC = [
    ("server/server.py", "server.py"),
    ("server/v1_adapter.py", "v1_adapter.py"),
    ("server/test_v1.py", "test_v1.py"),
]
DOC = ("docs/客户端框架说明.md", "客户端框架说明.md")
PORT = 8400
CLEAN = ("caremate.db", "caremate.db-wal", "caremate.db-shm", "acceptance.json",
         "server.log", "w.db", "w.db-wal", "w.db-shm")


def run(args, cwd=None, capture=True, env=None):
    return subprocess.run(args, cwd=cwd or ROOT, capture_output=capture, text=True,
                          encoding="utf-8", errors="replace", env=env)


def git(*args, cwd=None):
    return run(["git", "-c", "core.quotepath=false"] + list(args), cwd=cwd or ROOT)


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def sub_dir(worktree):
    """返回 server 文件所在目录（相对 worktree）：迭代分支在根，归档分支在子目录。"""
    if os.path.isdir(os.path.join(worktree, "caremate-cloud")):
        return "caremate-cloud"
    if os.path.isdir(os.path.join(worktree, "legacy-web")):
        return "legacy-web"
    return "server"      # web / qt：server/ 是仓库下的子目录


def copy_shared(worktree, with_tools=False):
    """把 main 的核心文件覆盖到分支；返回被覆盖的相对路径列表。"""
    sub = sub_dir(worktree)
    touched = []
    for src_rel, name in SYNC:
        src = os.path.join(ROOT, src_rel.replace("/", os.sep))
        dst = os.path.join(worktree, sub, name) if sub else os.path.join(worktree, name)
        if os.path.isfile(src):
            shutil.copyfile(src, dst)
            touched.append(os.path.relpath(dst, worktree).replace(os.sep, "/"))
    if with_tools:
        for src_rel in TOOL_FILES:
            src = os.path.join(ROOT, src_rel.replace("/", os.sep))
            dst = os.path.join(worktree, src_rel.replace("/", os.sep))
            if os.path.isfile(src):
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copyfile(src, dst)
                touched.append(src_rel)
    src_doc = os.path.join(ROOT, DOC[0].replace("/", os.sep))
    docs = os.path.join(worktree, "docs")
    dst = os.path.join(docs if os.path.isdir(docs) else worktree, DOC[1])
    # 只更新"分支里本来就有的"文档，不把 Qt 相关文档塞进 web 分支（保持 web 分支只有网页端）
    if os.path.isfile(src_doc) and os.path.isfile(dst):
        shutil.copyfile(src_doc, dst)
        touched.append(os.path.relpath(dst, worktree).replace(os.sep, "/"))
    return sub, touched


def verify(worktree, sub):
    """编译 + 起服务 + 两套验收；返回 (ok, 说明)。

    注意：`test_accept.py` 不会自己起服务（它先做健康检查），所以这里必须先启动，
    再依次跑 test_accept 与 test_v1——与 tools/verify_all.py 的做法一致。
    """
    server_dir = os.path.join(worktree, sub) if sub else worktree
    compile_proc = run([sys.executable, "-m", "py_compile", "server.py", "v1_adapter.py", "test_v1.py"],
                       cwd=server_dir)
    if compile_proc.returncode != 0:
        return False, "语法失败：%s" % (compile_proc.stderr or "").strip()[:120]

    db = os.path.join(tempfile.gettempdir(), "sync_branch_%d.db" % os.getpid())
    env = dict(os.environ, CAREMATE_DB=db, CAREMATE_TZ="Asia/Shanghai")
    proc = subprocess.Popen([sys.executable, "server.py", "--port", str(PORT)], cwd=server_dir,
                            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        ready = False
        for _ in range(60):
            try:
                with socket.create_connection(("127.0.0.1", PORT), timeout=0.5):
                    ready = True
                    break
            except OSError:
                time.sleep(0.25)
        if not ready:
            return False, "服务没起来（端口 %d 被占用？）" % PORT

        accept = run([sys.executable, "test_accept.py"], cwd=server_dir)
        accept_total = ""
        for line in (accept.stdout or "").splitlines():
            if "总计" in line:
                accept_total = line.strip()
        if accept.returncode != 0:
            return False, "test_accept 失败：%s" % (accept_total or (accept.stderr or "").strip()[:120])

        v1 = run([sys.executable, "test_v1.py"], cwd=server_dir,
                 env=dict(env, CAREMATE_API="http://127.0.0.1:%d" % PORT))
        v1_total = ""
        for line in (v1.stdout or "").splitlines():
            if "总计" in line:
                v1_total = line.strip()
        if v1.returncode != 0:
            return False, "test_v1 失败：%s" % (v1_total or (v1.stderr or "").strip()[:120])
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        for suffix in ("", "-wal", "-shm"):
            path = db + suffix
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
    return True, "%s；%s" % (accept_total or "accept 通过", v1_total or "v1 通过")


def clean_artifacts(worktree):
    for name in CLEAN:
        sub = sub_dir(worktree)
        candidates = {os.path.join(worktree, name)}
        if sub:
            candidates.add(os.path.join(worktree, sub, name))
        for path in candidates:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
    for dirpath, dirnames, _files in os.walk(worktree):
        if "__pycache__" in dirnames:
            shutil.rmtree(os.path.join(dirpath, "__pycache__"), ignore_errors=True)
            dirnames.remove("__pycache__")


def describe(rel, worktree):
    fixed = {
        "server.py": "服务端：三档升级链 + 端云同步三接口 + /v1 适配挂载",
        "v1_adapter.py": "颐伴手机端（Qt/QML）对接层：/v1/* 契约翻译到本分支的领域模型",
        "test_v1.py": "手机端 v1.1 契约验收 9 项",
        "客户端框架说明.md": "4.1 = Qt/QML 的依据与两套代码定位",
    }
    base = os.path.basename(rel)
    path = os.path.join(worktree, rel.replace("/", os.sep))
    if not os.path.isfile(path):
        return "移除（测试产物，不应入库）"
    if base in fixed:
        return fixed[base]
    path = os.path.join(worktree, rel.replace("/", os.sep))
    try:
        head = io.open(path, encoding="utf-8", errors="replace").read(3000)
    except OSError:
        return "同步 main 的最新实现"
    match = re.search(r"作用[：:]\s*(.+?)\s*(?:-->|--)?\s*$", head, re.M)
    return match.group(1).strip() if match else "同步 main 的最新实现"


def commit_all(worktree, branch):
    changed = [line[3:].strip().strip('"') for line in
               git("status", "--porcelain", cwd=worktree).stdout.splitlines()]
    committed = 0
    for rel in changed:
        msg = "%s：%s" % (rel, describe(rel, worktree))
        if len(msg) > 115:
            msg = msg[:112] + "..."
        git("add", "-A", "--", rel, cwd=worktree)
        if git("commit", "-q", "-m", msg, "--", rel, cwd=worktree).returncode == 0:
            committed += 1
            print("    提交 %s" % rel)
    print("  %s 提交 %d 个文件" % (branch, committed))
    return committed


def main():
    ap = argparse.ArgumentParser(description="把 main 的服务端核心同步到六条归档分支")
    ap.add_argument("--dry-run", action="store_true", help="只报告差异，不复制/提交/推送")
    ap.add_argument("--only", default="", help="逗号分隔的分支名")
    ap.add_argument("--with-tools", action="store_true",
                    help="同时同步 tools/（verify_all、publish、索引、P95、证据）")
    ap.add_argument("--keep", action="store_true", help="保留 worktree")
    args = ap.parse_args()

    branches = [b.strip() for b in args.only.split(",") if b.strip()] or BRANCHES
    git("fetch", "origin", "-q")
    results = []
    for branch in branches:
        print("\n=== %s ===" % branch)
        worktree = os.path.join(tempfile.gettempdir(), "syncbr_%s" % branch)
        if os.path.isdir(worktree):
            git("worktree", "remove", worktree, "--force")
        add = git("worktree", "add", "-f", worktree, branch)
        if add.returncode != 0:
            print("  无法创建 worktree：%s" % (add.stderr or "").strip()[:120])
            results.append((branch, "跳过", "worktree 失败"))
            continue

        sub, touched = copy_shared(worktree, with_tools=args.with_tools)
        changed = [line[3:].strip().strip('"')
                   for line in git("status", "--porcelain", cwd=worktree).stdout.splitlines()]
        if not changed:
            print("  已是最新（无需同步）")
            results.append((branch, "无变化", "已最新"))
            if not args.keep:
                git("worktree", "remove", worktree, "--force")
            continue
        print("  覆盖 %d 个文件：%s" % (len(changed), ", ".join(changed)))
        if args.dry_run:
            results.append((branch, "待同步", ", ".join(changed)))
            if not args.keep:
                git("worktree", "remove", worktree, "--force")
            continue

        ok, detail = verify(worktree, sub)
        clean_artifacts(worktree)
        print("  验证：%s —— %s" % ("通过" if ok else "失败", detail))
        if not ok:
            results.append((branch, "验证失败", detail))
            if not args.keep:
                git("worktree", "remove", worktree, "--force")
            continue

        commit_all(worktree, branch)
        results.append((branch, "已同步", detail))
        if not args.keep:
            git("worktree", "remove", worktree, "--force")

    if args.dry_run:
        print("\n[dry-run] 未提交、未推送。")
        return 0

    pending = [b for b, state, _ in results if state == "已同步"]
    if pending:
        print("\n=== 推送 %d 条分支 ===" % len(pending))
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from push_helper import push as smart_push
        for branch in pending:
            ok, message = smart_push(branch, ROOT)
            print("  %-14s %s" % (branch, message))

    print("\n=== 汇总 ===")
    for branch, state, detail in results:
        print("  %-14s %-8s %s" % (branch, state, detail[:70]))
    git("worktree", "prune")
    return 0 if all(state in ("无变化", "已同步") for _b, state, _d in results) else 1


if __name__ == "__main__":
    sys.exit(main())
