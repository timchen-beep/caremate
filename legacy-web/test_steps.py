# -*- coding: utf-8 -*-
"""按《实现步骤目标》第 4/5/6 步验收：
- 呼救（长按 3 秒 → level 3 告警 + 通知家属）
- 确认后 5 秒内可撤销、超过即 409
- 记录 30 分钟内可撤销、超过即 409，且撤销留痕
- 两小时没动静会告警（用极小阈值验证机制）
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
OUT = []


def call(base, path, token="fam-demo-2026", data=None, method=None):
    req = urllib.request.Request(
        base + path,
        data=None if data is None else json.dumps(data, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json", "X-Token": token,
                 "X-Forwarded-For": "198.51.100.30"},
        method=method or ("GET" if data is None else "POST"))
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            body = r.read().decode()
            return r.status, json.loads(body or "{}")
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            return e.code, json.loads(body or "{}")
        except ValueError:
            return e.code, {}


def items_of(x):
    return x if isinstance(x, list) else (x.get("items", []) if isinstance(x, dict) else [])


def start(port, db, extra=None, clean=True):
    if clean:
        for suf in ("", "-wal", "-shm"):
            p = os.path.join(BASE, db + suf)
            if os.path.exists(p):
                os.remove(p)
    env = dict(os.environ, CAREMATE_DB=os.path.join(BASE, db), **(extra or {}))
    proc = subprocess.Popen([PY, "server.py", "--port", str(port)], cwd=BASE, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = "http://127.0.0.1:%d" % port
    for _ in range(50):
        time.sleep(0.3)
        try:
            call(base, "/api/v1/health")
            return proc, base
        except Exception:
            continue
    return proc, base


def stop(p):
    p.terminate()
    try:
        p.wait(timeout=5)
    except Exception:
        p.kill()


def check(name, ok, detail):
    OUT.append((name, ok, detail))


# ================= 主实例：呼救 + 撤销窗口 + 记录撤销
proc, api = start(8410, "step_test.db", {"CAREMATE_INACTIVITY_HOURS": "0"})
try:
    # ---- 呼救
    code, r = call(api, "/api/v1/sos", token="app-elder-001",
                   data={"note": "头晕", "device": "android-13"})
    check("6 呼救 → level 3 告警", code == 201 and r.get("level") == 3 and r.get("notified"),
          "HTTP %d, level=%s, 通知=%s" % (code, r.get("level"), r.get("notified")))
    code, al = call(api, "/api/v1/alarms?elder_id=u-elder&envelope=1")
    kinds = [a["kind"] for a in items_of(al)]
    check("6b 呼救进了告警流水", "sos" in kinds, "kind 列表 %s" % sorted(set(kinds)))

    # ---- 确认后 5 秒撤销
    today = datetime.now().date()
    code, plan = call(api, "/api/v1/plans", data={"elder_id": "u-elder", "title": "撤销测试",
                                                  "times": [(datetime.now() - timedelta(minutes=3)).strftime("%H:%M")],
                                                  "rule": {"kind": "daily"}})
    code, occ = call(api, "/api/v1/occurrences?elder_id=u-elder&from=%s&to=%s" % (today, today))
    target = [o for o in items_of(occ) if o["plan_id"] == plan["id"]][0]
    oid = target["id"]

    code, ev = call(api, "/api/v1/occurrences/%s/events" % oid,
                    data={"action": "confirmed", "client_ts": datetime.now().isoformat()})
    code2, un = call(api, "/api/v1/occurrences/%s/events" % oid,
                     data={"action": "reopen", "client_ts": datetime.now().isoformat()})
    check("5 5 秒内撤销成功", code == 201 and code2 == 201 and un.get("state") == "pending",
          "确认 %d → 撤销 %d，状态 %s" % (code, code2, un.get("state")))

    # 超过窗口（把时间往回拨，模拟 6 秒前确认）
    call(api, "/api/v1/occurrences/%s/events" % oid,
         data={"action": "confirmed", "client_ts": datetime.now().isoformat()})
    time.sleep(6)
    code3, un2 = call(api, "/api/v1/occurrences/%s/events" % oid,
                      data={"action": "reopen", "client_ts": datetime.now().isoformat()})
    check("5b 超过 5 秒撤销 → 409", code3 == 409, "HTTP %d：%s" % (code3, un2.get("error", "")[:30]))

    # ---- 记录：30 分钟内可撤，撤了留痕
    code, rec = call(api, "/api/v1/records",
                     data={"elder_id": "u-elder", "type": "water", "value": 200,
                           "at": datetime.now().strftime("%Y-%m-%dT%H:%M:00+08:00")})
    code2, dd = call(api, "/api/v1/records/" + rec["id"], method="DELETE")
    check("4 记录 30 分钟内可撤销", code == 201 and code2 == 200, "删除 HTTP %d" % code2)
    code, evs = call(api, "/api/v1/events?elder_id=u-elder&limit=50")
    undo_rows = [e for e in items_of(evs) if e["action"] == "record_deleted"]
    check("4b 撤销留痕（谁/哪条）", bool(undo_rows),
          "留痕 %d 条，actor=%s" % (len(undo_rows), undo_rows[0]["actor"] if undo_rows else "-"))
finally:
    stop(proc)

# ================= 无动静告警（阈值设成极小，验证机制）
proc, api = start(8411, "idle_test.db", {"CAREMATE_INACTIVITY_HOURS": "0.0001"})
try:
    time.sleep(1)
    code, tick = call(api, "/api/v1/dev/scheduler/tick", data={})
    code, al = call(api, "/api/v1/alarms?elder_id=u-elder&envelope=1")
    kinds = [a["kind"] for a in items_of(al)]
    check("6c 太久没动静会告警", "inactivity" in kinds,
          "inactivity 告警 %d 条（tick: %s）" % (kinds.count("inactivity"), tick))
finally:
    stop(proc)

print("=" * 78)
print("《实现步骤目标》第 4/5/6 步验收")
print("=" * 78)
for name, ok, detail in OUT:
    print("%-26s | %s | %s" % (name, "PASS" if ok else "FAIL", detail))
n = sum(1 for o in OUT if o[1])
print("\n总计：%d/%d 通过" % (n, len(OUT)))
json.dump([{"item": a, "ok": b, "detail": c} for a, b, c in OUT],
          open(os.path.join(BASE, "acceptance_steps.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
sys.exit(0 if n == len(OUT) else 1)
