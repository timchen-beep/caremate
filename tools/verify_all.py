# 作用：一键全量验证：截断守卫 + 二进制魔数 + 语法 + 起服务 + 九套验收 + 产物卫生 + 四个页面 HTTP 检查（可选 flutter analyze）
# -*- coding: utf-8 -*-
"""一键全量验证：语法检查 + 九套验收 + 三个页面 HTTP 检查 + 完整性守卫。

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


# ---------------------------------------------------------------- 二进制完整性
BINARY_MAGIC = {
    ".png": b"\x89PNG",
    ".jpg": b"\xff\xd8",
    ".jpeg": b"\xff\xd8",
    ".jar": b"PK",
    ".apk": b"PK",
    ".aab": b"PK",
    ".ico": b"\x00\x00\x01\x00",
    ".db": b"SQLite format 3",
}


def check_binaries():
    """二进制文件必须以正确魔数开头。

    为什么需要这条：早期一个批量脚本用 encoding="utf-8", errors="replace" 读写**所有**文件，
    把 PNG 与 gradle-wrapper.jar 一并当文本处理，魔数被替换字符（efbfbd）覆盖——文件还在、
    大小也正常，但 AAPT 与 Gradle 直接失败。文本扫描发现不了，只有这里能发现。
    """
    try:
        files = subprocess.run(["git", "-C", ROOT, "-c", "core.quotepath=false", "ls-files"],
                               capture_output=True, text=True, encoding="utf-8").stdout.splitlines()
    except OSError:
        record("二进制完整性", True, "非 git 目录，跳过")
        return
    bad = []
    for rel in files:
        ext = os.path.splitext(rel)[1].lower()
        magic = BINARY_MAGIC.get(ext)
        if not magic:
            continue
        p = os.path.join(ROOT, rel.replace("/", os.sep))
        if not os.path.isfile(p):
            continue
        try:
            with open(p, "rb") as f:
                head = f.read(16)
        except OSError:
            continue
        if not head.startswith(magic):
            bad.append("%s（头 %s）" % (rel, head[:4].hex()))
    record("二进制完整性（PNG/JAR/APK 魔数）", not bad, "；".join(bad[:3]))


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


# ---------------------------------------------------------------- 产物卫生
def check_artifacts():
    """跑完测试后，仓库里不应出现"可以被提交"的测试产物。

    为什么需要：`test_accept.py` 会在 server/ 下建 caremate.db，若 .gitignore 漏了规则、
    或分支从别的仓库拷来时没带 .gitignore，`git add -A` 就会把测试库一起提交——
    本仓库历史上已经发生过三次（六条归档分支各一次）。这里提前拦住。
    """
    try:
        tracked = subprocess.run(["git", "-C", ROOT, "-c", "core.quotepath=false", "ls-files"],
                                 capture_output=True, text=True, encoding="utf-8").stdout.splitlines()
        status = subprocess.run(["git", "-C", ROOT, "-c", "core.quotepath=false", "status", "--porcelain"],
                                capture_output=True, text=True, encoding="utf-8").stdout.splitlines()
    except OSError:
        record("产物卫生", True, "非 git 目录，跳过")
        return

    bad_tracked = [p for p in tracked
                   if p.endswith((".db", ".db-wal", ".db-shm", ".pyc", "acceptance.json"))
                   or "__pycache__/" in p]
    stray = []
    for line in status:
        if not line.startswith("??"):
            continue
        p = line[3:].strip().strip('"')
        if p.endswith((".db", ".db-wal", ".db-shm", "acceptance.json")) or "__pycache__" in p:
            stray.append(p)

    detail = ""
    if bad_tracked:
        detail += "已入库：%s " % ", ".join(bad_tracked[:3])
    if stray:
        detail += "待提交产物：%s" % ", ".join(stray[:3])
    record("产物卫生（无 .db / __pycache__ 可入库）", not bad_tracked and not stray,
           detail or "干净")


# ---------------------------------------------------------------- 文档数字一致
CN_NUM = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6,
          "七": 7, "八": 8, "九": 9, "十": 10}

DOC_FILES = ["README.md", "GUIDE.md", "CONTRIBUTING.md",
             "tools/README.md", "docs/验收清单.md", "docs/评审答复_4.2.md"]


def check_doc_counts():
    """文档里写的「N 套验收」「verify_all 是 N 项」必须与实际一致。

    为什么需要：加了 test_sync 之后，全仓 12 处还写着「九套」，是人工扫出来的；
    这类数字对不上没法靠读代码发现，只能在这里比对。
    """
    problems = []
    expected_suites = len(SUITES)
    expected_items = len(RESULTS) + 1        # +1：本项守卫自身
    for rel in DOC_FILES:
        p = os.path.join(ROOT, rel.replace("/", os.sep))
        if not os.path.isfile(p):
            continue
        with io.open(p, encoding="utf-8", errors="replace") as f:
            for no, line in enumerate(f, 1):
                if "分支" in line:          # 分支说明里的套数不受 main 影响
                    continue
                for m in re.finditer(r"([一二三四五六七八九十\d]+)\s*套验收", line):
                    raw = m.group(1)
                    n = int(raw) if raw.isdigit() else CN_NUM.get(raw, -1)
                    if n != expected_suites:
                        problems.append("%s:%d 写 %s 套（应 %d）" % (rel, no, raw, expected_suites))
                for m in re.finditer(r"verify_all[^（\n]*（(\d+)\s*项", line):
                    n = int(m.group(1))
                    if n != expected_items:
                        problems.append("%s:%d 写 %d 项（应 %d）" % (rel, no, n, expected_items))
    record("文档数字一致（套数/项数）", not problems, "；".join(problems[:3]) or "一致")


# ---------------------------------------------------------------- 构建引用一致
SRC_EXT = (".cpp", ".cc", ".c", ".h", ".hpp", ".qml", ".ui", ".rc", ".dart")


def check_build_refs():
    """CMakeLists / pubspec 里引用的源文件必须存在，而且必须已被 git 追踪。

    为什么需要：有一次新增了 `qt/net/` 四个文件，本地能编译、`git status` 显示
    `?? qt/net/`（目录），逐文件提交脚本把它跳过了——远端仓库因此缺文件，
    但 CI 只跑 Python 测试，看不出来。这条守卫把"引用即必须入库"变成硬检查。
    """
    tracked = set(subprocess.run(
        ["git", "-C", ROOT, "-c", "core.quotepath=false", "ls-files"],
        capture_output=True, text=True, encoding="utf-8").stdout.splitlines())

    problems = []
    checked = 0
    for cmake in sorted(f for f in tracked if f.endswith("CMakeLists.txt")):
        base = os.path.dirname(os.path.join(ROOT, cmake.replace("/", os.sep)))
        try:
            text = io.open(os.path.join(base, "CMakeLists.txt"), encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        for m in re.finditer(r"[\w./-]+\.(?:cpp|cc|c|h|hpp|qml|ui|rc)\b", text):
            ref = m.group(0)
            if ref.startswith("/") or "$" in ref:
                continue
            target = os.path.normpath(os.path.join(base, ref))
            rel = os.path.relpath(target, ROOT).replace(os.sep, "/")
            checked += 1
            if not os.path.isfile(target):
                problems.append("%s 引用不存在的 %s" % (cmake, ref))
            elif rel not in tracked:
                problems.append("%s 引用的 %s 未入库" % (cmake, ref))

    # Flutter：pubspec 声明的目录下的 .dart 必须都在库里
    if "app/pubspec.yaml" in tracked:
        lib_dir = os.path.join(ROOT, "app", "lib")
        if os.path.isdir(lib_dir):
            for dirpath, _dirs, files in os.walk(lib_dir):
                for name in files:
                    if not name.endswith(".dart"):
                        continue
                    rel = os.path.relpath(os.path.join(dirpath, name), ROOT).replace(os.sep, "/")
                    checked += 1
                    if rel not in tracked:
                        problems.append("%s 未入库" % rel)

    record("构建引用一致（源文件存在且已入库）", not problems,
           "；".join(problems[:3]) or "检查 %d 处引用" % checked)


# ---------------------------------------------------------------- 3) 服务与九套
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
          "test_v06.py", "test_extra.py", "test_sync.py", "test_v1.py", "test_accept.py"]


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
    check_binaries()
    check_syntax()
    proc, db = run_server()
    try:
        run_suites()
        check_artifacts()
        check_build_refs()
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
    check_doc_counts()

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
