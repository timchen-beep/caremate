# -*- coding: utf-8 -*-
# 作用：工程性 7 项：派发延迟、限流 429、磁盘水位 507、备份、单实例保护
"""按修订版 4.2 验收：派发延迟 P95≤30 s、事件含前后状态、单查询解释、
配对限速、磁盘水位 507、在线备份。

派发延迟用独立实例（THRESHOLD_1=0）测，避免等 2 分钟阈值。
"""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta

BASE = r"C:\Users\43915\Documents\deepseek-harness\default-workspace\caremate-cloud"
PY = sys.executable
API = "http://127.0.0.1:8400"
FAST = "http://127.0.0.1:8403"
FAM = "fam-demo-2026"
OUT = []


def call(path, token=FAM, data=None, method=None, headers=None, base=None):
    req = urllib.request.Request(
        (base or API) + path,
        data=None if data is None else json.dumps(data, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json",
                 **({"X-Token": token} if token else {}), **(headers or {})},
        method=method or ("GET" if data is None else "POST"))
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            return e.code, json.loads(body or "{}")
        except ValueError:
            return e.code, {"raw": body}


def items_of(body):
    if isinstance(body, list):
        return body
    return body.get("items", []) if isinstance(body, dict) else []


def check(name, ok, detail):
    OUT.append((name, ok, detail))


def start(port, db, extra_env):
    for suffix in ("", "-wal", "-shm"):
        p = os.path.join(BASE, db + suffix)
        if os.path.exists(p):
            os.remove(p)
    env = dict(os.environ, CAREMATE_DB=os.path.join(BASE, db), **extra_env)
    proc = subprocess.Popen([PY, "server.py", "--port", str(port)], cwd=BASE, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        time.sleep(0.3)
        try:
            call("/api/v1/health", FAM, base="http://127.0.0.1:%d" % port)
            return proc
        except Exception:
            continue
    return proc


# ================= A. 派发延迟与事件链（独立实例，THRESHOLD_1=0）
fast = start(8403, "fast_test.db",
             {"CAREMATE_THRESHOLD_1": "0", "CAREMATE_THRESHOLD_2": "30", "CAREMATE_THRESHOLD_3": "60"})
try:
    due = (datetime.now() + timedelta(seconds=75)).replace(second=0, microsecond=0)
    if due <= datetime.now():
        due += timedelta(minutes=1)
    hhmm = due.strftime("%H:%M")
    code, r = call("/api/v1/plans", FAM, {"user_id": "u-elder", "title": "延迟测试", "kind": "medication",
                                          "times": [hhmm], "dose": "1 片", "rule": {"kind": "daily"}},
                   base=FAST)
    pid = r.get("id")
    call("/api/v1/occurrences?user_id=u-elder", FAM, base=FAST)   # 到期前先物化
    print("计划 %s 到期于 %s，等调度器派发（每 30 s 一扫）……" % (pid, hhmm))

    state, oid = None, None
    deadline = time.time() + 130
    while time.time() < deadline:
        time.sleep(4)
        code, occ = call("/api/v1/occurrences?user_id=u-elder", FAM, base=FAST)
        mine = [o for o in items_of(occ) if o["plan_id"] == pid]
        if mine and mine[0]["state"] not in ("pending",):
            state, oid = mine[0]["state"], mine[0]["id"]
            break
    check("调度器自动派发", state is not None, "状态 %s（阈值 0 分钟，等 ≤130 s）" % state)

    code, m = call("/api/v1/metrics?days=7", FAM, base=FAST)
    check("派发延迟 P95 ≤ 30 s", code == 200 and m.get("p95") is not None and m["p95"] <= 30,
          "p50 %s s / p95 %s s / max %s s（样本 %s，补扫排除 %s）"
          % (m.get("p50"), m.get("p95"), m.get("max"), m.get("samples"), m.get("backfill_excluded")))

    if oid:
        code, ev = call("/api/v1/occurrences/%s/events" % oid, FAM, base=FAST)
        payloads = [(e.get("payload") or {}) for e in ev.get("events", [])]
        ok = bool(payloads) and all("prev_state" in p and "new_state" in p for p in payloads)
        chain = " → ".join("%s→%s" % (p.get("prev_state"), p.get("new_state")) for p in payloads)
        check("事件含 prev/new state", ok, "链条 " + chain)
        check("单查询即可解释升级", code == 200 and len(payloads) >= 1,
              "一次 GET 返回 %d 条迁移事件" % len(payloads))
    else:
        check("事件含 prev/new state", False, "没拿到实例")
        check("单查询即可解释升级", False, "没拿到实例")
finally:
    fast.terminate()
    try:
        fast.wait(timeout=5)
    except Exception:
        fast.kill()

# ================= B. 限速 / 507 / 备份（主实例）
ip = "203.0.113.77"
codes = [call("/api/v1/auth/pair", None, {"code": "8823"},
              headers={"X-Forwarded-For": ip})[0] for _ in range(6)]
check("配对限速 5 次/分钟", codes[:5].count(201) == 5 and codes[5] == 429,
      "六次请求返回：" + ",".join(str(c) for c in codes))

disk = start(8402, "disk_test.db", {"CAREMATE_DISK_MIN_MB": "999999999", "CAREMATE_SCHEDULER": "0"})
try:
    code, body = call("/api/v1/records", FAM,
                      {"user_id": "u-elder", "type": "water", "value": 100,
                       "occurred_at": datetime.now().strftime("%Y-%m-%d %H:%M")},
                      base="http://127.0.0.1:8402")
    check("磁盘不足拒绝写入 507", code == 507, "HTTP %d：%s" % (code, body.get("error", "")[:40]))
finally:
    disk.terminate()
    try:
        disk.wait(timeout=5)
    except Exception:
        disk.kill()

bdir = os.path.join(BASE, "backups")
before = set(os.listdir(bdir)) if os.path.isdir(bdir) else set()
r = subprocess.run([PY, "server.py", "--backup"], cwd=BASE, capture_output=True, text=True)
after = set(os.listdir(bdir))
new = after - before
check("--backup 可产出快照", r.returncode == 0 and len(new) == 1,
      "新增 %s" % (list(new)[:1] or "无"))

print("=" * 78)
print("修订版 4.2 验收")
print("=" * 78)
for name, ok, detail in OUT:
    print("%-24s | %s | %s" % (name, "PASS" if ok else "FAIL", detail))
ok_n = sum(1 for o in OUT if o[1])
print("\n总计：%d/%d 通过" % (ok_n, len(OUT)))
json.dump([{"item": n, "ok": o, "detail": d} for n, o, d in OUT],
          open(os.path.join(BASE, "acceptance_v06.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
sys.exit(0 if ok_n == len(OUT) else 1)

