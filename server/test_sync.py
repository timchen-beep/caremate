# -*- coding: utf-8 -*-
# 作用：端云同步验收 5 项：批量上行、幂等去重、越权拒绝、回灌游标、端侧告警
"""按 4.1 架构图第 5 层验收：POST /v1/events、GET /v1/state?since=、POST /v1/alarm。

前置：服务已在 127.0.0.1:8400 运行（python test_sync.py 会先等健康检查）。
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = os.environ.get("CAREMATE_API") or "http://127.0.0.1:8400"
FAM, APP = "fam-demo-2026", "app-elder-001"
RESULTS = []


def call(path, token, data=None, timeout=10):
    req = urllib.request.Request(
        API + path,
        data=None if data is None else json.dumps(data, ensure_ascii=False).encode("utf-8"),
        headers={"X-Token": token, "Content-Type": "application/json"},
        method="GET" if data is None else "POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8") or "{}")


def check(name, ok, detail):
    RESULTS.append((name, ok, detail))


def wait_up():
    for _ in range(40):
        try:
            if call("/api/v1/health", FAM)[0] == 200:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def main():
    if not wait_up():
        print("服务没起来，先 python server.py --port %d" % 8400)
        return 1

    # 自建一个"干净"实例：不从已有列表里挑，避免被其它套件改过状态
    from datetime import datetime, timedelta
    slot = (datetime.now() - timedelta(minutes=1)).strftime("%H:%M")
    plan = call("/api/v1/plans", FAM, {"user_id": "u-elder", "title": "同步测试用计划",
                                       "kind": "medication", "times": [slot], "dose": "1 片",
                                       "rule": {"kind": "daily"}})[1]
    call("/api/v1/occurrences?user_id=u-elder", FAM)   # 物化
    occ = [o for o in call("/api/v1/occurrences?user_id=u-elder", FAM)[1]
           if o.get("plan_id") == plan["id"]]
    if not occ:
        print("没拿到测试实例")
        return 1
    oid = occ[0]["id"]

    # ① 批量上行三条不同事件
    batch = [{"occurrence_id": oid, "action": a, "client_ts": "2026-11-10T0%d:00:00+08:00" % (i + 1),
              "event_id": "sync-test-%d" % i} for i, a in enumerate(("snoozed", "snoozed", "confirmed"))]
    st, r = call("/api/v1/events", APP, {"events": batch})
    check("POST /events 批量上行", st == 200 and r.get("accepted") == 3 and not r.get("rejected"),
          "accepted=%s duplicates=%s rejected=%s" % (r.get("accepted"), r.get("duplicates"), r.get("rejected")))

    # ② 重放最后一条（confirmed）→ 判重，不新增
    #    注意不能整批重放：末条已把实例置为 confirmed，再重放 snoozed 会（正确地）被判 409
    st, r2 = call("/api/v1/events", APP, {"events": [batch[-1]]})
    check("重放幂等（不新增）", st == 200 and r2.get("duplicates") == 1 and r2.get("accepted") == 0,
          "accepted=%s duplicates=%s" % (r2.get("accepted"), r2.get("duplicates")))

    # ③ 非法与越权：不存在的实例、非法 action
    st, r3 = call("/api/v1/events", APP, {"events": [
        {"occurrence_id": "no-such-id", "action": "confirmed", "client_ts": "x", "event_id": "e1"},
        {"occurrence_id": oid, "action": "escalated", "client_ts": "y", "event_id": "e2"},
    ]})
    reasons = " | ".join(x.get("reason", "") for x in r3.get("rejected", []))
    check("非法请求逐条拒绝", st == 200 and len(r3.get("rejected", [])) == 2,
          "rejected=%d：%s" % (len(r3.get("rejected", [])), reasons[:80]))

    # ④ 回灌游标：先全量，再用 next_since 拉一次应无新增
    st, s1 = call("/api/v1/state?since=1970-01-01T00:00:00Z", FAM)
    cursor = s1.get("next_since") or ""
    st2, s2 = call("/api/v1/state?since=%s" % urllib.parse.quote(cursor), FAM)
    check("GET /state 游标推进", st == 200 and st2 == 200 and len(s1.get("occurrences", [])) > 0
          and len(s2.get("occurrences", [])) == 0,
          "首次 %d 条，游标 %s，二次 %d 条"
          % (len(s1.get("occurrences", [])), cursor[:19], len(s2.get("occurrences", []))))

    # ⑤ 端侧告警：直接上报 SOS，应立刻落库并出现在 /alarms
    st, a = call("/api/v1/alarm", APP, {"kind": "sos", "note": "同步测试呼救", "device": "test"})
    alarms = call("/api/v1/alarms?user_id=u-elder", FAM)[1]
    hits = [x for x in (alarms if isinstance(alarms, list) else alarms.get("items", []))
            if x.get("id") == (a.get("alarm") or {}).get("id")]
    check("POST /alarm 立刻可见", st == 201 and len(hits) == 1,
          "status=%s alarm_id=%s" % (st, (a.get("alarm") or {}).get("id")))

    width = max(len(r[0]) for r in RESULTS)
    print("=" * 70)
    print("端云同步验收（4.1 架构图第 5 层）")
    print("=" * 70)
    allok = True
    for name, ok, detail in RESULTS:
        allok = allok and ok
        print("%-*s | %s | %s" % (width, name, "PASS" if ok else "FAIL", detail))
    print("\n总计：%d/%d 通过" % (sum(1 for r in RESULTS if r[1]), len(RESULTS)))
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main())