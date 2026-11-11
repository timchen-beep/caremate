# -*- coding: utf-8 -*-
# 作用：颐伴手机端（Qt/QML）v1.1 契约验收：7 个 /v1/* 接口 + 4 份 fixtures 形状 + 端上 ID 公式
"""端上契约验收（对齐 fspro7967/yiban_android_app 的 docs/fixtures/*.json）。

9 项：
1. 形状：GET /v1/state 的 occurrence 字段（与 state_since.json 逐键比对）
2. 形状：GET /v1/plans 的 plan 字段（与 plans_since.json 逐键比对）
3. 游标：同一次变化的第二次拉取返回空（增量语义）
4. 事件：POST /v1/events 单条 → 201 {accepted:true, server_seq}
5. 去重：同一 event_id 再来 → 200 {accepted:false, dedup:true}，序号不增
6. 冲突：对已确认实例再 confirm → 409 {error:{code:state_conflict,…}}（error_conflict.json 形状）
7. 配对：POST /v1/pair 用 6 位码换 token + cursor
8. 告警：POST /v1/alarm（occurrence_id 可空、source=manual）→ {sent, channel}
9. ID 公式：端上算的 occurrenceId 能反查到我们下发的同一条
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = os.environ.get("CAREMATE_API") or "http://127.0.0.1:8400"
ELDER = "app-elder-001"
FAM = "fam-demo-2026"
RESULTS = []

STATE_KEYS = {"occurrence_id", "plan_id", "title", "dose", "note", "due_ts", "state",
              "snooze_count", "snooze_until_ts", "window_min", "escalate_after_min",
              "updated_seq", "last_event_id"}
PLAN_KEYS = {"plan_id", "title", "dose", "note", "rule", "window_min", "escalate_after_min",
             "version", "deleted", "updated_seq"}


def call(path, token=ELDER, data=None, method=None, timeout=10):
    req = urllib.request.Request(
        API + path,
        data=None if data is None else json.dumps(data, ensure_ascii=False).encode("utf-8"),
        headers={"X-Token": token, "Content-Type": "application/json"},
        method=method or ("GET" if data is None else "POST"),
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
        print("服务没起来，先 python server.py --port 8400")
        return 1

    # 先自建一条计划（不依赖其它套件留下的数据；时间设为一分钟前，保证已到点）
    from datetime import datetime, timedelta
    hhmm = (datetime.now() - timedelta(minutes=1)).strftime("%H:%M")
    st, mine = call("/v1/plans", data={"title": "契约测试-%s" % hhmm, "dose": "1 片", "note": "",
                                       "rule": {"kind": "daily", "times": [hhmm]},
                                       "window_min": 30, "escalate_after_min": 15})
    my_plan = mine.get("plan_id") if st == 201 else None

    # ①② 形状
    st, state = call("/v1/state?since=0")
    occs = state.get("occurrences") or []
    ok_shape = st == 200 and occs and STATE_KEYS <= set(occs[0].keys())
    missing = "" if ok_shape else "缺 %s" % (STATE_KEYS - set(occs[0].keys()) if occs else "全部")
    check("GET /v1/state 形状", ok_shape,
          "%d 条；next_seq=%s；%s" % (len(occs), state.get("next_seq"), missing or "字段齐全"))

    st, plans = call("/v1/plans?since=0")
    pl = plans.get("plans") or []
    ok_plan = st == 200 and pl and PLAN_KEYS <= set(pl[0].keys())
    check("GET /v1/plans 形状", ok_plan,
          "%d 条；next_seq=%s；rule.kind=%s" % (len(pl), plans.get("next_seq"),
                                                (pl[0].get("rule") or {}).get("kind") if pl else "-"))

    # ③ 游标增量：用 next_seq 再拉，不应有新数据
    cursor = state.get("next_seq") or 0
    st2, state2 = call("/v1/state?since=%d" % cursor)
    check("游标增量（二次为空）", st2 == 200 and len(state2.get("occurrences") or []) == 0,
          "cursor=%s 二次 %d 条" % (cursor, len(state2.get("occurrences") or [])))

    if not occs:
        print("没有任何实例：/v1/state 物化失败，检查 ensure_occurrences")
        return 1

    # ④⑤ 事件 + 去重：优先用自己刚建的这条（避免撞上其它套件改过的终态）
    mine_occs = [o for o in occs if my_plan and o["plan_id"] == my_plan]
    target = next((o for o in mine_occs if o["state"] in ("pending", "notified")),
                  next((o for o in occs if o["state"] in ("pending", "notified")), occs[0]))
    eid = "fixture-%d" % int(time.time())
    st, ack = call("/v1/events", data={"event_id": eid, "occurrence_id": target["occurrence_id"],
                                       "action": "confirm", "ts": int(time.time() * 1000),
                                       "device_id": "test-device"})
    ok_ev = st == 201 and ack.get("accepted") is True and isinstance(ack.get("server_seq"), int)
    check("POST /v1/events 单条", ok_ev, "status=%s body=%s" % (st, json.dumps(ack, ensure_ascii=False)[:80]))

    st, ack2 = call("/v1/events", data={"event_id": eid, "occurrence_id": target["occurrence_id"],
                                        "action": "confirm", "ts": 0, "device_id": "test-device"})
    ok_dedup = st == 200 and ack2.get("accepted") is False and ack2.get("dedup") is True
    check("event_id 去重", ok_dedup and ack2.get("server_seq") == ack.get("server_seq"),
          "status=%s dedup=%s seq=%s（原 %s）" % (st, ack2.get("dedup"),
                                                 ack2.get("server_seq"), ack.get("server_seq")))

    # ⑥ 冲突：对刚确认的实例再 confirm → 409 且形状符合 error_conflict.json
    st, conflict = call("/v1/events", data={"event_id": eid + "-x",
                                            "occurrence_id": target["occurrence_id"],
                                            "action": "miss", "ts": 0, "device_id": "test-device"})
    err = (conflict or {}).get("error") or {}
    ok_conf = st == 409 and err.get("code") == "state_conflict" and "server_state" in err
    check("409 冲突形状", ok_conf, "status=%s code=%s state=%s" % (st, err.get("code"), err.get("server_state")))

    # ⑦ 配对：6 位码换 token
    st, pair = call("/v1/pair", token=FAM, data={"pair_code": "8823", "device_id": "android-test", "role": "elder"})
    ok_pair = st == 200 and str(pair.get("token", "")).startswith("ses-") and pair.get("device_id") == "android-test"
    check("POST /v1/pair", ok_pair, "status=%s cursor=%s" % (st, pair.get("cursor")))

    # ⑧ 告警：SOS（occurrence_id 可空 + source=manual）
    st, alarm = call("/v1/alarm", data={"occurrence_id": None, "source": "manual", "level": 3,
                                        "ts": int(time.time() * 1000), "device_id": "android-test",
                                        "reason": "测试呼救"})
    check("POST /v1/alarm（SOS）", st == 200 and alarm.get("sent") is True,
          "status=%s channel=%s" % (st, alarm.get("channel")))

    # ⑨ ID 公式：端上按 planId*1e9 + (julianDay%1e7)*100 + 序号 算出的 id 应能在 /v1/state 里找到
    from datetime import datetime
    o = occs[0]
    due = datetime.fromtimestamp(o["due_ts"] / 1000.0)
    julian = due.date().toordinal() + 1721425
    guess = o["plan_id"] * 1000000000 + (julian % 10000000) * 100
    found = [x for x in occs if x["plan_id"] == o["plan_id"]
             and abs(x["occurrence_id"] - guess) < 100]
    check("端上 ID 公式可反查", bool(found),
          "公式基准 %d，同计划实例 %d 条" % (guess, len(found)))

    width = max(len(r[0]) for r in RESULTS)
    print("=" * 70)
    print("手机端 v1.1 契约验收（yiban_android_app）")
    print("=" * 70)
    allok = True
    for name, ok, detail in RESULTS:
        allok = allok and ok
        print("%-*s | %s | %s" % (width, name, "PASS" if ok else "FAIL", detail))
    print("\n总计：%d/%d 通过" % (sum(1 for r in RESULTS if r[1]), len(RESULTS)))
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main())
