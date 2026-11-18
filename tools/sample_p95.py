# 作用：一键取 P95 真实样本：干净端口 + 临时库 → 建 40 秒后的计划 → 等调度器派发 → 打印派发延迟
"""用法：

    python tools/sample_p95.py               # 默认等 90 秒
    python tools/sample_p95.py --wait 60

为什么需要它：/metrics 的派发延迟只统计「到期前就已物化」的实例（前向派发），
回填数据不计入，所以演示库/测试库里 p50/p95 恒为 null。本脚本造一个真实的前向样本。

脚本会：
1. 找空闲端口、独立临时数据库，避免和已在跑的服务/旧库冲突；
2. 起服务，建一个 40 秒后的计划；
3. 等调度器（默认 30 秒一拍）派发；
4. 读 /api/v1/metrics，打印 samples / p50 / p95 / max；
5. 收尾：停服务、删临时库。
"""
import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER = os.path.join(ROOT, "server")
TOKEN = os.environ.get("CAREMATE_DEMO_TOKEN", "fam-demo-2026")


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def call(base, path, token=None, data=None):
    req = urllib.request.Request(
        base + path,
        data=None if data is None else json.dumps(data, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", **({"X-Token": token} if token else {})},
        method="GET" if data is None else "POST",
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode("utf-8") or "{}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wait", type=int, default=90, help="建计划后等待派发的秒数")
    args = ap.parse_args()

    port = free_port()
    base = "http://127.0.0.1:%d" % port
    db = os.path.join(tempfile.gettempdir(), "caremate_p95_%d.db" % port)
    env = dict(os.environ, CAREMATE_DB=db, CAREMATE_TZ="Asia/Shanghai",
               PYTHONIOENCODING="utf-8")
    proc = subprocess.Popen([sys.executable, "server.py", "--port", str(port)],
                            cwd=SERVER, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(40):
            try:
                call(base, "/api/v1/health")
                break
            except Exception:
                time.sleep(0.5)
        else:
            print("服务没起来")
            return 1

        # 对齐到"下一分钟"之后：若取当前分钟，due_at 已经过去，会被判成回填（不计入 P95）
        now = datetime.now()
        due = (now + timedelta(seconds=90)).replace(second=0, microsecond=0)
        slot = due.strftime("%H:%M")
        # 通知要等「迟到 >= th1」才触发（默认 2 分钟），所以必须等够 th1 + 一拍
        # 方案 B 之后：到点即 notified，只需等到期 + 一拍调度（TICK=30 s）
        wait = int((due - now).total_seconds()) + 45
        print("端口 %d，临时库 %s" % (port, os.path.basename(db)))
        print("现在 %s，建 %s 的计划（距到期 %d 秒），等待 %d 秒让调度器在到点后派发"
              % (now.strftime("%H:%M:%S"), slot, int((due - now).total_seconds()), wait))
        call(base, "/api/v1/plans", TOKEN, {
            "user_id": "u-elder", "title": "P95 采样", "kind": "medication",
            "times": [slot], "dose": "1 片", "rule": {"kind": "daily"},
        })
        # 关键：实例是"查询时物化"的，不查就不会进 occurrences 表，调度器扫不到
        call(base, "/api/v1/occurrences?user_id=u-elder", TOKEN)
        print("已物化实例（此时 created_at < due_at，才算前向派发）")
        time.sleep(max(wait, args.wait))
        m = call(base, "/api/v1/metrics", TOKEN)
        if m.get("samples", 0) == 0:
            print("仍未取到样本（可能调度器还没跑到，或时钟未到）。再等一会儿重跑：")
            print(json.dumps(m, ensure_ascii=False))
            return 2
        print("样本数：%d（回填排除 %d）" % (m["samples"], m.get("backfill_excluded", 0)))
        print("p50 = %s s   p95 = %s s   max = %s s   调度周期 = %s s"
              % (m.get("p50"), m.get("p95"), m.get("max"), m.get("tick_seconds")))
        verdict = "PASS（≤ 30 s）" if (m.get("p95") or 0) <= 30 else "FAIL（> 30 s）"
        print("口径：派发延迟 = notified_at - due_at_utc，只含前向派发；结论：%s" % verdict)
        return 0
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


if __name__ == "__main__":
    sys.exit(main())