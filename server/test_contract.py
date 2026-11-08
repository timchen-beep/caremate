# -*- coding: utf-8 -*-
# 作用：契约验收 18 项：鉴权、from/to、事件提交幂等、数组/信封、错误码
"""按《手机端对接契约 v0.1》逐条验收：七个接口 + 认证 + 字段名 + 错误码。"""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta

BASE = os.environ.get("CAREMATE_BASE") or os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
API = "http://127.0.0.1:8400"
OUT = []


def req(path, token=None, data=None, method=None, base=None):
    headers = {"Content-Type": "application/json", "X-Forwarded-For": "198.51.100.12"}
    if token:
        headers["Authorization"] = "Bearer " + token
    r = urllib.request.Request((base or API) + path,
                               data=None if data is None else json.dumps(data, ensure_ascii=False).encode(),
                               headers=headers,
                               method=method or ("GET" if data is None else "POST"))
    try:
        with urllib.request.urlopen(r, timeout=15) as resp:
            body = resp.read().decode()
            try:
                return resp.status, json.loads(body or "{}")
            except ValueError:
                return resp.status, body
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            return e.code, json.loads(body or "{}")
        except ValueError:
            return e.code, {"raw": body}


def check(name, ok, detail):
    OUT.append((name, ok, detail))


def wait_up():
    for _ in range(50):
        time.sleep(0.3)
        try:
            req("/api/v1/health")
            return True
        except Exception:
            continue
    return False


if not wait_up():
    print("服务没起来")
    sys.exit(1)

# ---------- 1) POST /auth/pair：pairing_code → elder_id, token
code, r = req("/api/v1/auth/pair", data={"pairing_code": "8823"})
tok = r.get("token", "")
check("1 配对（pairing_code → token）", code in (200, 201) and bool(tok) and r.get("elder_id") == "u-elder",
      "HTTP %d, elder_id=%s, token=%s…" % (code, r.get("elder_id"), tok[:10]))

# 令牌走 Authorization: Bearer
code, me = req("/api/v1/me", token=tok)
check("令牌走 Authorization: Bearer", code == 200 and me.get("role") == "family", "HTTP %d" % code)

# ---------- 2) POST /plans：返回 plan 对象；rule 用契约写法
today = datetime.now().date()
code, plan = req("/api/v1/plans", token=tok, data={
    "elder_id": "u-elder", "title": "契约测试-氨氯地平", "times": ["2026-11-05T08:00:00+08:00"],
    "rule": {"kind": "daily"}, "dose": "1 片", "active": True})
check("2 建计划返回 plan 对象", code == 201 and plan.get("id") and plan.get("times") == ["08:00"],
      "HTTP %d, id=%s, times=%s" % (code, plan.get("id"), plan.get("times")))
pid = plan.get("id")

code, plan2 = req("/api/v1/plans/" + pid, token=tok, method="PATCH",
                  data={"title": "契约测试-改名", "times": ["09:15"]})
check("PATCH /plans/{id} 返回 plan", code == 200 and plan2.get("title") == "契约测试-改名"
      and plan2.get("times") == ["09:15"], "title=%s times=%s" % (plan2.get("title"), plan2.get("times")))

# 七种规则都能建（含契约别名 meal_offset / once.at）
rules = [{"kind": "daily"}, {"kind": "interval", "n": 2, "start": today.isoformat()},
         {"kind": "weekly", "weekdays": [1, 3, 5]},
         {"kind": "monthly", "day": 5},
         {"kind": "course", "days": 7, "start": today.isoformat()},
         {"kind": "meal_offset", "offset_minutes": 30, "anchor": "lunch"},
         {"kind": "once", "at": (today + timedelta(days=2)).isoformat() + "T09:30:00+08:00"}]
bad = []
for i, rule in enumerate(rules):
    code, _ = req("/api/v1/plans", token=tok, data={"elder_id": "u-elder", "title": "规则%d" % i,
                                                    "times": ["09:30"], "rule": rule})
    if code != 201:
        bad.append((rule.get("kind"), code))
check("2b 七种规则（含 meal_offset / once.at）", not bad, "失败：%s" % (bad or "无"))

code, err = req("/api/v1/plans", token=tok, data={"elder_id": "u-elder", "title": "坏规则",
                                                  "times": ["09:30"], "rule": {"kind": "yearly"}})
check("参数不合法返回 422", code == 422, "HTTP %d" % code)

# ---------- 3) GET /occurrences：elder_id + from/to，返回数组
code, occ = req("/api/v1/occurrences?elder_id=u-elder&from=%s&to=%s" % (today, today), token=tok)
is_list = isinstance(occ, list)
check("3 查实例（elder_id + from/to，返回数组）", code == 200 and is_list and len(occ) > 0,
      "HTTP %d, %s" % (code, "数组 %d 条" % len(occ) if is_list else type(occ).__name__))

# ---------- 4) POST /occurrences/{id}/events：客户端 event_id、幂等、409
target = [o for o in occ if o["state"] in ("pending", "notified", "escalated", "missed")][0]
oid = target["id"]
ts = datetime.now().isoformat(timespec="seconds") + "+08:00"
eid = "ev-" + uuid.uuid4().hex[:10]
code, ev1 = req("/api/v1/occurrences/%s/events" % oid, token=tok,
                data={"action": "confirmed", "event_id": eid, "client_ts": ts, "note": "契约测试"})
check("4 提交事件返回 event 对象", code == 201 and (ev1.get("event") or {}).get("event_id") == eid,
      "HTTP %d, event_id=%s, duplicate=%s" % (code, (ev1.get("event") or {}).get("event_id"), ev1.get("duplicate")))

code, ev2 = req("/api/v1/occurrences/%s/events" % oid, token=tok,
                data={"action": "confirmed", "event_id": eid, "client_ts": ts})
check("4b 重复提交 duplicate=true", code == 201 and ev2.get("duplicate") is True,
      "HTTP %d, duplicate=%s" % (code, ev2.get("duplicate")))

code, ev3 = req("/api/v1/occurrences/%s/events" % oid, token=tok,
                data={"action": "missed", "event_id": "ev-" + uuid.uuid4().hex[:8],
                      "client_ts": datetime.now().isoformat()})
check("4c 已确认又报未确认 → 409", code == 409, "HTTP %d：%s" % (code, ev3.get("error", "")[:30]))

code, ev4 = req("/api/v1/occurrences/not-a-real-id/events", token=tok,
                data={"action": "confirmed", "client_ts": "x"})
check("实例不存在 → 404", code == 404, "HTTP %d" % code)

# ---------- 5) POST /records（at 用 ISO）+ PATCH 更正
code, rec = req("/api/v1/records", token=tok, data={
    "elder_id": "u-elder", "type": "water", "value": 200, "unit": "ml",
    "at": datetime.now().strftime("%Y-%m-%dT%H:%M:00+08:00")})
check("5 新增记录返回 record", code == 201 and rec.get("id") and rec.get("at"),
      "HTTP %d, id=%s, at=%s" % (code, rec.get("id"), rec.get("at")))
rid = rec.get("id")

code, rec2 = req("/api/v1/records/" + rid, token=tok, method="PATCH", data={"value": 250})
check("5b 更正返回新 record（不覆盖）", code == 200 and rec2.get("id") != rid and rec2.get("value") == 250,
      "旧 %s → 新 %s, value=%s" % (rid[:8], str(rec2.get("id"))[:8], rec2.get("value")))

# ---------- 6) GET /stats：range=7d，daily/weekly
code, st = req("/api/v1/stats?elder_id=u-elder&range=7d", token=tok)
check("6 统计（range=7d，daily/weekly）",
      code == 200 and isinstance(st.get("daily"), list) and isinstance(st.get("weekly"), list)
      and st.get("range") == "7d",
      "HTTP %d, daily %d 天, weekly %d 周" % (code, len(st.get("daily", [])), len(st.get("weekly", []))))

code, st30 = req("/api/v1/stats?elder_id=u-elder&range=30d", token=tok)
check("6b range=30d", code == 200 and st30.get("range") == "30d", "range=%s" % st30.get("range"))

# ---------- 7) GET /alerts：数组
code, al = req("/api/v1/alerts?elder_id=u-elder", token=tok)
check("7 告警列表返回数组", code == 200 and isinstance(al, list), "HTTP %d, %s"
      % (code, "数组 %d 条" % len(al) if isinstance(al, list) else type(al).__name__))

# ---------- 8) 错误码 401 / 403
code, _ = req("/api/v1/occurrences?elder_id=u-elder")
check("无令牌 → 401", code == 401, "HTTP %d" % code)
code, _ = req("/api/v1/occurrences?elder_id=u-other", token=tok)
check("跨家庭 → 403", code == 403, "HTTP %d" % code)

print("=" * 78)
print("手机端对接契约 v0.1 验收")
print("=" * 78)
for name, ok, detail in OUT:
    print("%-34s | %s | %s" % (name, "PASS" if ok else "FAIL", detail))
n = sum(1 for o in OUT if o[1])
print("\n总计：%d/%d 通过" % (n, len(OUT)))
json.dump([{"item": a, "ok": b, "detail": c} for a, b, c in OUT],
          open(os.path.join(BASE, "acceptance_contract.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
sys.exit(0 if n == len(OUT) else 1)
