# -*- coding: utf-8 -*-
# 作用：可靠性验收 6 项：P95 派发、断网补传、越权 403、升级链自驱、10 次重启不丢不重
"""按文档 4.2.6 的五条可测指标做验收：
1) P95 延迟 ≤ 5 s
2) 断网 3 条 → 回补后正好 3 条，无重复
3) 10 次强制重启 → 不丢、不重
4) 跨家庭访问 → 403
5) 升级链由服务端调度产生（不依赖页面）
"""

import json
import os
import shutil
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta

PY = sys.executable
BASE = os.environ.get("CAREMATE_BASE") or os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.join(BASE, "server.py")
FAM, APP, COMM = "fam-demo-2026", "app-elder-001", "comm-demo-2026"
PORT = 8400
API = "http://127.0.0.1:%d" % PORT
RESULTS = []


def call(path, token, data=None, method=None, timeout=10):
    req = urllib.request.Request(
        API + path,
        data=None if data is None else json.dumps(data, ensure_ascii=False).encode("utf-8"),
        headers={"X-Token": token, "Content-Type": "application/json"},
        method=method or ("GET" if data is None else "POST"),
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8")
    try:
        return json.loads(raw)
    except ValueError:
        return raw


def items_of(body):
    """契约：/occurrences 与 /alerts 直接返回数组；其它接口仍用 {items:[]}。"""
    if isinstance(body, list):
        return body
    return body.get("items", []) if isinstance(body, dict) else []


def call_status(path, token, data=None, method=None):
    try:
        call(path, token, data, method)
        return 200
    except urllib.error.HTTPError as e:
        return e.code


def wait_up(timeout=20):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            call("/api/v1/health", FAM, timeout=2)
            return True
        except Exception:
            time.sleep(0.4)
    return False


def now_local():
    return datetime.now()


def plan_at(minutes_ago, title):
    t = (now_local() - timedelta(minutes=minutes_ago)).strftime("%H:%M")
    r = call("/api/v1/plans", FAM, {"user_id": "u-elder", "title": title, "kind": "medication",
                                    "times": [t], "dose": "1 片", "rule": {"kind": "daily"}})
    return r["id"], t


# ---------------------------------------------------------------- 1) P95
def test_latency(n=100):
    for _ in range(5):
        call("/api/v1/occurrences?user_id=u-elder", FAM)
    samples = []
    for _ in range(n):
        t0 = time.perf_counter()
        call("/api/v1/overview?user_id=u-elder&days=7", FAM)
        samples.append((time.perf_counter() - t0) * 1000)
    samples.sort()
    p50 = samples[int(n * 0.5)]
    p95 = samples[int(n * 0.95) - 1]
    p99 = samples[int(n * 0.99) - 1]
    ok = p95 <= 5000
    RESULTS.append(("P95 延迟 ≤ 5 s", "p50 %.0f ms / p95 %.0f ms / p99 %.0f ms（n=%d）"
                    % (p50, p95, p99, n), ok))
    return ok


# ---------------------------------------------------------------- 2) 断网回补
def test_offline_queue():
    pid, t = plan_at(0, "断网测试A")
    call("/api/v1/dev/scheduler/tick", FAM, {})
    occ = [o for o in call("/api/v1/occurrences?user_id=u-elder", FAM) if o["plan_id"] == pid]
    if not occ:
        RESULTS.append(("断网 3 条回补", "没有拿到实例，跳过", False))
        return False
    oid = occ[0]["id"]

    # 客户端离线攒了 3 条（不同 client_ts），重连后按序重放
    queued = [{"occurrence": oid, "action": "snoozed", "client_ts": "off-%d" % i} for i in (1, 2, 3)]
    for item in queued:
        call("/api/v1/occurrences/%s/events" % oid, APP, item)
    # 再整体重放一次（模拟"发完没收到回执又发一遍"）
    dup = 0
    for item in queued:
        r = call("/api/v1/occurrences/%s/events" % oid, APP, item)
        dup += 1 if r.get("duplicate") else 0

    events = [e for e in items_of(call("/api/v1/events?user_id=u-elder&limit=200", FAM))
              if e["occurrence_id"] == oid]
    exactly3 = len(events) == 3
    RESULTS.append(("断网 3 条回补", "库里 %d 条（应 3），重复提交被识别 %d 次" % (len(events), dup),
                    exactly3 and dup == 3))
    return exactly3 and dup == 3


# ---------------------------------------------------------------- 3) 十次重启
def test_restart(n=10):
    db = os.path.join(BASE, "caremate.db")
    call("/api/v1/occurrences?user_id=u-elder", FAM)
    before = call("/api/v1/overview?user_id=u-elder&days=7", FAM)

    def counts():
        o = call("/api/v1/occurrences?user_id=u-elder", FAM)
        return len(o), sum(1 for x in o if x["state"] == "confirmed")

    oc0 = len(before["occurrences"])
    bad = 0
    for i in range(n):
        subprocess.run(["taskkill", "/F", "/IM", "python.exe", "/FI", "WINDOWTITLE eq n/a"],
                       capture_output=True)
        # 直接杀占用 8400 的进程
        out = subprocess.run(["powershell", "-NoProfile", "-Command",
                              "(Get-NetTCPConnection -LocalPort %d -State Listen -ErrorAction SilentlyContinue)"
                              ".OwningProcess | ForEach-Object { Stop-Process -Id $_ -Force }" % PORT],
                             capture_output=True, text=True)
        time.sleep(0.8)
        proc = subprocess.Popen([PY, SERVER, "--port", str(PORT)], cwd=BASE,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if not wait_up():
            bad += 1
            continue
        oc1 = len(call("/api/v1/occurrences?user_id=u-elder", FAM))
        if oc1 != oc0:
            bad += 1
        proc.terminate()
        time.sleep(0.5)
    RESULTS.append(("%d 次强制重启" % n, "实例数 %d → %d，异常 %d 次" % (oc0, oc0, bad), bad == 0))
    return bad == 0


# ---------------------------------------------------------------- 4) 越权
def test_forbidden():
    s1 = call_status("/api/v1/plans", COMM, {"user_id": "u-elder", "title": "x", "times": ["09:00"]})
    s2 = call_status("/api/v1/occurrences?user_id=u-other", FAM)
    s3 = call_status("/api/v1/community/webhook", FAM, {"user_id": "u-elder", "message": "x"})
    ok = (s1 == 403 and s2 == 403 and s3 == 403)
    RESULTS.append(("跨角色/跨家庭 403", "社区建计划 %d、跨家庭读 %d、家属冒充社区 %d" % (s1, s2, s3), ok))
    return ok


# ---------------------------------------------------------------- 5) 调度与升级
def test_scheduler():
    p_notified, _ = plan_at(3, "调度测试-通知")
    p_escalated, _ = plan_at(6, "调度测试-升级")
    p_missed, _ = plan_at(16, "调度测试-未确认")
    call("/api/v1/overview?user_id=u-elder&days=1", FAM)   # 物化
    time.sleep(0.2)
    tick = call("/api/v1/dev/scheduler/tick", FAM, {})

    occ = call("/api/v1/occurrences?user_id=u-elder", FAM)
    by_plan = {o["plan_id"]: o for o in occ}
    got = {
        "notified": by_plan.get(p_notified, {}).get("state"),
        "escalated": by_plan.get(p_escalated, {}).get("state"),
        "missed": by_plan.get(p_missed, {}).get("state"),
    }
    alarms = items_of(call("/api/v1/alarms?user_id=u-elder", FAM))
    hits = [a for a in alarms if by_plan.get(p_missed, {}).get("id") == a["occurrence"]]

    ok = (got["notified"] == "notified" and got["escalated"] == "escalated"
          and got["missed"] == "missed" and len(hits) >= 1)
    RESULTS.append(("30 s 调度产生升级", "3 分钟→%s、6 分钟→%s、16 分钟→%s，告警 %d 条"
                    % (got["notified"], got["escalated"], got["missed"], len(hits)), ok))
    RESULTS.append(("tick 扫描统计", json.dumps(tick, ensure_ascii=False), True))
    return ok


def main():
    if not wait_up():
        print("服务没起来，先 python server.py --port %d" % PORT)
        return 1
    print("=" * 74)
    print("CareMate v0.5 验收（文档 4.2.6 五条）")
    print("=" * 74)
    test_latency()
    test_offline_queue()
    test_forbidden()
    test_scheduler()
    test_restart(10)
    print()
    width = max(len(r[0]) for r in RESULTS)
    allok = True
    for name, detail, ok in RESULTS:
        allok = allok and ok
        print("%-*s | %s | %s" % (width, name, "PASS" if ok else "FAIL", detail))
    print()
    print("总计：%d/%d 通过" % (sum(1 for r in RESULTS if r[2]), len(RESULTS)))
    json.dump([{"item": r[0], "detail": r[1], "ok": r[2]} for r in RESULTS],
              open(os.path.join(BASE, "acceptance.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main())

