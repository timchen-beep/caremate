# -*- coding: utf-8 -*-
"""一键全量验证：语法检查 + 七套验收 + 三个页面 HTTP 检查 + 完整性守卫。

用法:
    python tools/verify_all.py              # 标准验证
    python tools/verify_all.py --flutter    # 额外跑 flutter analyze

任何一项失败 → 退出码 1（CI 的 acceptance 工作流跑的是同一套脚本）。
"""
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER = os.path.join(ROOT, "server")
PORT = 8400
BASE = "http://127.0.0.1:%d" % PORT
USE_FLUTTER = "--flutter" in sys.argv

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

RESULTS = []


def record(name, ok, detail=""):
    RESULTS.append((name, ok, detail))
    print("%-48s %s %s" % (name, "PASS" if ok else "FAIL", detail))


# ---------------------------------------------------------------- 1) 完整性守卫
def check_truncation():
    """对比工作区与 HEAD 的文件大小，找出被异常截断的文本文件（批量脚本事故的护栏）。"""
    try:
        files = subprocess.run(["git", "-C", ROOT, "-c", "core.quotepath=false", "ls-files"],
                               capture_output=True, text=True, encoding="utf-8").stdout.splitlines()
    except OSError:
        record("完整性守卫", True, "非 git 目录，跳过")
        return
    bad = []
    for rel in files:
        if not rel.lower().endswith((".py", ".html", ".js", ".dart", ".md", ".sh", ".qml", ".cpp")):
            continue
        p = os.path.join(ROOT, rel.replace("/", os.sep))
        if not os.path.isfile(p):
            continue
        old = subprocess.run(["git", "-C", ROOT, "cat-file", "-s", "HEAD:%s" % rel],
                             capture_output=True, text=True, encoding="utf-8").stdout.strip()
        if not old.isdigit():
            continue
        now = os.path.getsize(p)
        if int(old) - now > 1000:      # 少了 1 KB 以上：很可能被截断
            bad.append("%s %d→%d" % (rel, int(old), now))
    record("完整性守卫（文件没被截断）", not bad, "；".join(bad[:3]))


# ---------------------------------------------------------------- 2) 语法
def check_syntax():
    bad = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in (".git", "build", ".dart_tool")]
        for n in filenames:
            if n.endswith(".py"):
                p = os.path.join(dirpath, n)
                r = subprocess.run([sys.executable, "-m", "py_compile", p], capture_output=True)
                if r.returncode != 0:
                    bad.append(os.path.relpath(p, ROOT))
    record("Python 语法", not bad, "；".join(bad[:3]))

    bash = shutil.which("bash")
    if not bash and os.name == "nt":
        for cand in (r"C:\Program Files\Git\bin\bash.exe",
                     r"C:\Program Files (x86)\Git\bin\bash.exe",
                     r"C:\msys64\usr\bin\bash.exe"):
            if os.path.exists(cand):
                bash = cand
                break
    if not bash:
        record("Shell 语法", True, "未找到 bash，跳过")
        return
    bad = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for n in filenames:
            if n.endswith(".sh"):
                p = os.path.join(dirpath, n)
                r = subprocess.run([bash, "-n", p], capture_output=True)
                if r.returncode != 0:
                    bad.append(os.path.relpath(p, ROOT))
    record("Shell 语法", not bad, "；".join(bad[:3]))


# ---------------------------------------------------------------- 3) 服务与七套
def wait_health(timeout=30):
    for _ in range(timeout * 2):
        try:
            with urllib.request.urlopen(BASE + "/api/v1/health", timeout=2) as r:
                return r.status == 200
        except Exception:
            time.sleep(0.5)
    return False


def run_server():
    db = os.path.join(tempfile.gettempdir(), "caremate_verify.db")
    for suf in ("", "-wal", "-shm"):
        p = db + suf
        if os.path.exists(p):
            os.remove(p)
    env = dict(os.environ, CAREMATE_DB=db, CAREMATE_TZ="Asia/Shanghai")
    proc = subprocess.Popen([sys.executable, "server.py", "--port", str(PORT)],
                            cwd=SERVER, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ok = wait_health()
    record("服务启动（%s）" % BASE, ok, "" if ok else "健康检查失败")
    return proc, db


SUITES = ["test_contract.py", "test_p2.py", "test_align.py", "test_steps.py",
          "test_v06.py", "test_extra.py", "test_accept.py"]


def run_suites():
    # 子进程统一输出 UTF-8，否则 Windows 下是 GBK，判定与显示都会乱
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    for suite in SUITES:
        r = subprocess.run([sys.executable, suite], cwd=SERVER, env=env,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        tail = [l for l in r.stdout.strip().splitlines() if l.strip()]
        line = tail[-1].strip() if tail else ""
        # 判定只看退出码（套件全过返回 0），文字仅用于展示
        ok = r.returncode == 0
        record(suite, ok, line[-40:] if line else "退出码 %d" % r.returncode)


# ---------------------------------------------------------------- 4) 页面
PAGES = [
    ("/dashboard", 30000, "watchAlarms"),
    ("/app", 20000, "speak"),
    ("/kiosk", 4000, "呼救"),
    ("/", 2000, "CareMate"),
]


def check_pages():
    for path, min_size, marker in PAGES:
        try:
            with urllib.request.urlopen(BASE + path, timeout=10) as r:
                body = r.read().decode("utf-8", "replace")
            ok = r.status == 200 and len(body.encode()) >= min_size and marker in body
            record("页面 %s" % path, ok,
                   "%d 字节%s" % (len(body.encode()), "" if marker in body else "（少了 %s）" % marker))
        except Exception as exc:
            record("页面 %s" % path, False, str(exc)[:60])


# ---------------------------------------------------------------- 5) Flutter
def check_flutter():
    flutter = shutil.which("flutter")
    app = os.path.join(ROOT, "app")
    if not flutter or not os.path.isdir(app):
        record("Flutter analyze", True, "环境没有 flutter，跳过")
        return
    r = subprocess.run([flutter, "analyze"], cwd=app, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    ok = r.returncode == 0
    record("Flutter analyze", ok, (r.stdout or "").strip().splitlines()[-1][:50] if r.stdout else "")


def main():
    print("=" * 78)
    print("CareMate 全量验证")
    print("=" * 78)
    check_truncation()
    check_syntax()
    proc, db = run_server()
    try:
        run_suites()
        check_pages()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        for suf in ("", "-wal", "-shm"):
            p = db + suf
            if os.path.exists(p):
                os.remove(p)
    if USE_FLUTTER:
        check_flutter()

    print("-" * 78)
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    total = len(RESULTS)
    print("总计：%d/%d 通过" % (passed, total))
    if passed != total:
        print("失败项：")
        for name, ok, detail in RESULTS:
            if not ok:
                print("   - %s：%s" % (name, detail))
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
