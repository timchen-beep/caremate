# -*- coding: utf-8 -*-
# 作用：一致性 9 项：from/to 反序 400、改计划历史不变、换时区不新增行、单入口检查
"""按《接口与实现决策清单》验收：
- /occurrences?from=&to=
- 改计划后历史不变（快照）
- 换时区只重算到期，不新增行（实例身份 = 本地墙钟）
- 全局只有一处写 state
"""

import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta

BASE = os.environ.get("CAREMATE_BASE") or os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
FAM = "fam-demo-2026"
OUT = []


def call(base, path, token=FAM, data=None, method=None):
    req = urllib.request.Request(
        base + path,
        data=None if data is None else json.dumps(data, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json", "X-Forwarded-For": "198.51.100.14", **( {"X-Token": token} if token else {})},
        method=method or ("GET" if data is None else "POST"))
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def items_of(body):
    if isinstance(body, list):
        return body
    return body.get("items", []) if isinstance(body, dict) else []


def check(name, ok, detail):
    OUT.append((name, ok, detail))


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


def stop(proc):
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.kill()


# ================= 1) from/to
proc, api = start(8405, "align_test.db")
try:
    today = datetime.now().date()
    code, r = call(api, "/api/v1/occurrences?user_id=u-elder&from=%s&to=%s" % (today, today + timedelta(days=1)))
    ok = code == 200 and isinstance(r, list) and len(r) > 0
    spans = sorted({i["date_local"] for i in r})
    check("GET /occurrences?from=&to=", ok, "%d 条，覆盖 %s" % (len(r) if isinstance(r, list) else -1, spans))

    code, r2 = call(api, "/api/v1/occurrences?user_id=u-elder&from=2026-01-02&to=2026-01-01")
    check("from/to 反序报 400", code == 400, "HTTP %d：%s" % (code, r2.get("error")))

    # ================= 2) 改计划后历史不变
    hh = (datetime.now() - timedelta(minutes=30)).strftime("%H:%M")
    code, pl = call(api, "/api/v1/plans", data={"user_id": "u-elder", "title": "改名前-氨氯地平",
                                               "kind": "medication", "times": [hh], "dose": "1 片",
                                               "rule": {"kind": "daily"}})
    pid = pl["id"]
    code, occ = call(api, "/api/v1/occurrences?user_id=u-elder&from=%s&to=%s" % (today, today))
    before = [o for o in (occ if isinstance(occ, list) else occ.get("items", [])) if o["plan_id"] == pid][0]
    # 改计划：改名 + 改时刻 + 改剂量
    call(api, "/api/v1/plans/" + pid, method="PATCH",
         data={"user_id": "u-elder", "title": "改名后-缬沙坦", "kind": "medication",
               "times": ["23:50"], "dose": "2 片", "rule": {"kind": "daily"}})
    code, occ2 = call(api, "/api/v1/occurrences?user_id=u-elder&from=%s&to=%s" % (today, today))
    same_slot = [o for o in occ2 if o["slot_local"] == before["slot_local"]]
    after = same_slot[0] if same_slot else {}
    new_slots = [o["slot_local"] for o in occ2 if o["plan_id"] == pid]
    same = bool(after) and (after["title"] == before["title"] and after["dose"] == before["dose"]
                            and after["state"] == before["state"])
    check("改计划后历史不变（快照）", same,
          "原实例 %s @%s 仍在（标题 %s、剂量 %s）；改后计划的时刻已变为 %s"
          % (before["title"], before["slot_local"], after.get("title"), after.get("dose"), new_slots[-1:]))
finally:
    stop(proc)

# ================= 3) 换时区不重复（同一份库，两个时区）
sh = None
ny = None
try:
    sh, api = start(8405, "tz_test.db")
    call(api, "/api/v1/occurrences?user_id=u-elder&from=%s&to=%s" % (datetime.now().date(), datetime.now().date()))
    code, occ_sh = call(api, "/api/v1/occurrences?user_id=u-elder&from=%s&to=%s"
                        % (datetime.now().date() + timedelta(days=1),
                           datetime.now().date() + timedelta(days=1)))
    code, m1 = call(api, "/api/v1/metrics")
    n1 = sum((m1.get("states") or {}).values())
    slots1 = sorted(o["slot_local"] for o in occ_sh)
    sample1 = {o["slot_local"]: o["due_at_utc"] for o in occ_sh}
    stop(sh)

    ny, api = start(8405, "tz_test.db", {"CAREMATE_TZ": "America/New_York"}, clean=False)
    call(api, "/api/v1/occurrences?user_id=u-elder&from=%s&to=%s"
         % (datetime.now().date(), datetime.now().date()))
    code, occ_ny = call(api, "/api/v1/occurrences?user_id=u-elder&from=%s&to=%s"
                        % (datetime.now().date() + timedelta(days=1),
                           datetime.now().date() + timedelta(days=1)))
    code, m2 = call(api, "/api/v1/metrics")
    n2 = sum((m2.get("states") or {}).values())
    check("换时区不新增实例行", n1 == n2, "上海 %d 行 → 纽约 %d 行（同样的查询顺序）" % (n1, n2))

    code, health = call(api, "/api/v1/health")
    check("服务报告当前时区", health.get("tz") == "America/New_York", "tz=%s" % health.get("tz"))

    slots2 = sorted(o["slot_local"] for o in occ_ny)
    check("同一墙钟仍是同一实例（明天）", slots1 == slots2 and len(slots2) > 0,
          "上海 %s / 纽约 %s" % (slots1, slots2))

    recomputed = sum(1 for o in occ_ny
                     if sample1.get(o["slot_local"]) and sample1[o["slot_local"]] != o["due_at_utc"])
    check("到期时刻按新时区重算", recomputed > 0,
          "%d 条 due_at 由 %s 前改为新时区" % (recomputed, "上海"))
    neg = [o for o in occ_ny if o["late_min"] < 0]
    check("不出现负数倒计时", not neg, "late_min 全部 ≥0")
finally:
    for p in (sh, ny):
        if p:
            try:
                stop(p)
            except Exception:
                pass

# ================= 4) 唯一状态入口（静态检查）
src = open(os.path.join(BASE, "server.py"), encoding="utf-8").read()
writes = re.findall(r"UPDATE\s+occurrences\s+SET\s+[^\"']*state\s*=", src, re.I)
check("全局只有一处写 state", len(writes) == 1, "命中 %d 处（应 1）" % len(writes))

print("=" * 78)
print("《接口与实现决策清单》对齐验收")
print("=" * 78)
for name, ok, detail in OUT:
    print("%-26s | %s | %s" % (name, "PASS" if ok else "FAIL", detail))
n_ok = sum(1 for o in OUT if o[1])
print("\n总计：%d/%d 通过" % (n_ok, len(OUT)))
json.dump([{"item": n, "ok": o, "detail": d} for n, o, d in OUT],
          open(os.path.join(BASE, "acceptance_align.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
sys.exit(0 if n_ok == len(OUT) else 1)
