# -*- coding: utf-8 -*-
# 作用：跑九套验收并把结果汇总成一份 markdown 证据文件（自动定位仓库、缺套件就报错，不再产出"0/0 通过"的假证据）
"""证据包：跑九套验收 + 抓关键数字，生成一份验收汇总 markdown。

用法（先起后端，默认 8400）：
    python server.py --port 8400          # 另一个窗口
    python tools/collect_evidence.py      # 默认写到 %TEMP%\\caremate_evidence\\
    python tools/collect_evidence.py -o evidence   # 也可以指定输出目录
"""

import argparse
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # 仓库根（本文件在 tools/ 下）
SERVER = os.path.join(ROOT, "server")
PY = sys.executable
API = os.environ.get("CAREMATE_API") or "http://127.0.0.1:8400"

# 九套：名字 → 覆盖范围（与 server/ 下的文件名一一对应）
SUITES = [
    ("test_contract", "手机端对接契约 v0.1 七条 + 认证 + 错误码"),
    ("test_p2", "配对换 token、越界、one-off、登出"),
    ("test_align", "from/to、历史不变、换时区不重复、单入口"),
    ("test_steps", "呼救、5 秒撤销、记录撤销留痕、无动静告警"),
    ("test_v06", "派发延迟、事件前后状态、限速、507、备份"),
    ("test_extra", "越权、导出、告警确认、社区 webhook"),
    ("test_sync", "端云同步三条接口（上行事件 / 下行增量 / 呼救）"),
    ("test_v1", "手机族 /v1/* 七个端点与 ID 映射"),
    ("test_accept", "4.2.6 五条（接口延迟、重放、10 次重启、403、升级链）"),
]


def alive(timeout=3):
    try:
        with urllib.request.urlopen(API + "/api/v1/health", timeout=timeout) as r:
            return r.status == 200
    except (urllib.error.URLError, OSError):
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default=os.path.join(os.environ.get("TEMP", "."), "caremate_evidence"),
                    help="输出目录（默认 %%TEMP%%\\caremate_evidence，别往仓库里写）")
    ap.add_argument("--api", default=API, help="被测后端地址")
    args = ap.parse_args()

    missing = [s for s, _ in SUITES if not os.path.exists(os.path.join(SERVER, s + ".py"))]
    if missing:
        print("缺少套件文件：%s（不在 %s 下）" % (", ".join(missing), SERVER))
        return 2

    # 没有后端就自己起一个（临时库），这样每次都是干净数据；
    # 复用别人已在跑的后端时会带历史数据，个别断言（如"重放不新增"）会假失败。
    own = None
    db = os.path.join(os.environ.get("TEMP", "."), "caremate_evidence.db")
    if not alive():
        for leftover in (db, db + "-wal", db + "-shm"):
            if os.path.exists(leftover):
                os.remove(leftover)
        env = dict(os.environ, PYTHONIOENCODING="utf-8", CAREMATE_TZ="Asia/Shanghai",
                   CAREMATE_SKIP_ENV="1", CAREMATE_DB=db)
        own = subprocess.Popen([PY, "-X", "utf8", "server.py", "--port", "8400"], cwd=SERVER, env=env,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(30):
            if alive():
                break
            time.sleep(0.5)
        if not alive():
            print("起了自己的后端还是连不上 %s，先手动跑 python server.py --port 8400 看一眼" % args.api)
            own.terminate()
            return 2
        print("已用临时库起后端：%s（跑完自动关）" % db)
    else:
        print("复用已在跑的后端 %s；如果它不是干净库，个别断言可能假失败" % args.api)

    version = "?"
    with open(os.path.join(SERVER, "server.py"), encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("VERSION ="):
                version = line.split("=")[1].strip().strip('"')
                break

    lines = ["# CareMate 验收汇总（%s）" % date.today().isoformat(), "",
             "后端：`server/server.py` v%s ｜ 被测地址：%s" % (version, args.api), "",
             "| 套件 | 覆盖 | 结果 |", "|---|---|---|"]
    total_ok = total_all = 0
    details = []
    failed = []
    run_env = dict(os.environ, PYTHONIOENCODING="utf-8", CAREMATE_TZ="Asia/Shanghai",
                   CAREMATE_SKIP_ENV="1", CAREMATE_API=args.api)
    if own is not None:
        run_env["CAREMATE_DB"] = db        # 套件里自起服务的用例也要落在同一个临时库
    try:
        for suite, cover in SUITES:
            path = os.path.join(SERVER, suite + ".py")
            # 注意：CAREMATE_BASE 在套件里是**目录**（有的套件用它做 cwd 起自己的服务），
            # 想改被测地址用 CAREMATE_API；多数套件仍固定 8400，所以本工具默认就跑 8400。
            proc = subprocess.run([PY, "-X", "utf8", path], cwd=SERVER, capture_output=True,
                                  text=True, encoding="utf-8", errors="replace", env=run_env)
            out = (proc.stdout or "") + (proc.stderr or "")
            summary = ""
            for line in out.splitlines():
                if "总计：" in line:
                    summary = line.strip()
            if not summary and proc.returncode != 0:
                summary = "崩溃：%s" % (out.strip().splitlines()[-1] if out.strip() else "无输出")
            ok = tot = 0
            if summary:
                try:
                    ok, tot = [int(x) for x in summary.replace("总计：", "").replace(" 通过", "").split("/")]
                except ValueError:
                    ok = tot = 0
            if tot == 0 or proc.returncode != 0:
                failed.append(suite)
            total_ok += ok
            total_all += tot
            lines.append("| `%s.py` | %s | %s |" % (suite, cover,
                                                    summary.replace("总计：", "") if summary else "未取到结果"))
            details.append((suite, out))
    finally:
        if own is not None:
            own.terminate()
            try:
                own.wait(timeout=10)
            except subprocess.TimeoutExpired:
                own.kill()

    lines += ["", "**合计 %d/%d 通过。**" % (total_ok, total_all), "", "## 关键数字", ""]
    for suite, out in details:
        for line in out.splitlines():
            if "PASS" in line and any(k in line for k in ("p95", "p50", "重启", "幂等", "回补", "派发", "升级")):
                lines.append("- " + line.strip())
    lines += ["", "## 复现命令", "", "```bash",
              "python server/server.py --port 8400",
              "python tools/collect_evidence.py", "```", "",
              "> 验收用默认阈值 2/5/15 分钟（2 分钟没确认 → 通知家属，5 分钟 → 再提醒一次，15 分钟 → 记未确认）；"
              "`--demo` 会把阈值改成 1/3/10、等会儿 5 分钟，**只用于演示**，别和验收混用。"]

    os.makedirs(args.out, exist_ok=True)
    outfile = os.path.join(args.out, "验收汇总_%s.md" % date.today().strftime("%Y%m%d"))
    with open(outfile, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print("wrote:", outfile)
    print("合计 %d/%d 通过" % (total_ok, total_all))
    if failed:
        print("有套件失败或没取到结果：%s" % ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
