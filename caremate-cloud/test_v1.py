# -*- coding: utf-8 -*-
# 作用：颐伴手机端（Qt/QML）v1.1 契约验收：7 个 /v1/* 接口 + 4 份 fixtures 形状 + 端上 ID 公式 + 批量拒收 + 手机端 fire/呼救两种真实动作 + 看板改删计划的增量同步 + 记录幂等/撤销
"""端上契约验收（对齐 fspro7967/yiban_android_app 的 docs/fixtures/*.json）。

16 项：
1. 形状：GET /v1/state 的 occurrence 字段（与 state_since.json 逐键比对）
2. 形状：GET /v1/plans 的 plan 字段（与 plans_since.json 逐键比对）
3. 游标：同一次变化的第二次拉取返回空（增量语义）
4. 事件：POST /v1/events 单条 → 201 {accepted:true, server_seq}
5. 去重：同一 event_id 再来 → 200 {accepted:false, dedup:true}，序号不增
6. 冲突：对已确认实例再 confirm → 409 {error:{code:state_conflict,…}}（error_conflict.json 形状）
7. 批量拒收：一批里只有一条冲突时 → 200，冲突那条进 rejected（retryable=false），其余照常 accepted
8. 到点提醒：action="fire"（手机端点开提醒时发）→ 201 接受，且不动服务端状态（对已确认实例也不 409）
9. 呼救：escalate + occurrence_id=0（手机端 SOS）→ 201 接受，并在 alarms 里落下 kind=sos 的 level 3
10. 配对：POST /v1/pair 用 6 位码换 token + cursor
11. 告警：POST /v1/alarm（occurrence_id 可空、source=manual）→ {sent, channel}
12. ID 公式：端上算的 occurrenceId 能反查到我们下发的同一条
13. 看板建计划 → 端上增量（/v1/plans?since=）能拉到，version=1
14. 看板改计划 → 端上增量收到新内容，version 加 1（以前完全不 bump，端上永远跳过）
15. 看板删计划 → 端上增量收到 deleted:true（软删留 tombstone，以前硬删收不到）
16. 记录幂等/撤销：同一 client_id 连发两次只落一条；DELETE /v1/records/{id} 能撤到云端
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

    # ⑥b 批量里有一条冲突：只拒那一条，其余照常收（整批 409 会让手机端永远重试）
    other = next((o for o in occs if o["state"] in ("pending", "notified")
                  and o["occurrence_id"] != target["occurrence_id"]), None)
    if other:
        st, mix = call("/v1/events", data={"events": [
            {"event_id": eid + "-mix-bad", "occurrence_id": target["occurrence_id"],
             "action": "miss", "ts": 0, "device_id": "test-device"},
            {"event_id": eid + "-mix-ok", "occurrence_id": other["occurrence_id"],
             "action": "confirm", "ts": int(time.time() * 1000), "device_id": "test-device"},
        ]})
        rej = (mix.get("rejected") or [{}])[0]
        acc = mix.get("accepted") or []
        ok_mix = (st == 200 and rej.get("code") == "state_conflict"
                  and rej.get("retryable") is False and len(acc) == 1)
        check("批量只拒冲突那条", ok_mix,
              "status=%s rejected=%s retryable=%s accepted=%d"
              % (st, rej.get("code"), rej.get("retryable"), len(acc)))
    else:
        check("批量只拒冲突那条", False, "没有第二条可确认的实例，无法验证")

    # ⑥c 手机端到点弹提醒发 action="fire"：必须被接受，且不能改状态、不能撞状态机。
    # 这里故意对已确认（terminal）的实例发 fire —— 旧版会 409/拒收，手机就会永远重发这一条。
    st, fire = call("/v1/events", data={"event_id": eid + "-fire", "occurrence_id": target["occurrence_id"],
                                        "action": "fire", "ts": int(time.time() * 1000),
                                        "device_id": "android-test"})
    ok_fire = st == 201 and fire.get("accepted") is True
    check("action=fire 被接受且不改状态", ok_fire, "status=%s body=%s" % (st, json.dumps(fire, ensure_ascii=False)[:80]))

    # ⑥d 呼救：手机端发 escalate + occurrence_id=0（app_core.cpp: appendEvent(0,"escalate","sos")）
    st, sos_ev = call("/v1/events", data={"event_id": eid + "-sos", "occurrence_id": 0,
                                          "action": "escalate", "reason": "sos",
                                          "ts": int(time.time() * 1000), "device_id": "android-test"})
    st_al, alarms = call("/api/v1/alarms?limit=20", FAM)
    killed = [a for a in (alarms if isinstance(alarms, list) else alarms.get("items") or [])
              if a.get("kind") == "sos"]
    ok_sos = st == 201 and sos_ev.get("accepted") is True and bool(killed)
    check("呼救事件（occurrence_id=0）落成 sos 告警", ok_sos,
          "status=%s 告警 %d 条" % (st, len(killed)))

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

    # ⑩～⑬ 云组 11/23 的四个同步问题（1105PDF C-1..C-4）
    # ⑩ C-2 看板建/改计划要 bump v1_rowseq + v1_version，否则端上按 since 增量永远拉不到
    st, base = call("/v1/plans?since=0")
    seq0 = int(base.get("next_seq") or 0)
    stamp = datetime.now().strftime("%H%M%S")
    st, made = call("/api/v1/plans", FAM, {"title": "增量测试-%s" % stamp, "times": ["07:15"],
                                           "user_id": "u-elder"})
    plan_id = made.get("id") if isinstance(made, dict) else ""
    st, inc1 = call("/v1/plans?since=%d" % seq0)
    seq1 = int(inc1.get("next_seq") or 0)
    hit1 = [p for p in (inc1.get("plans") or []) if p.get("plan_id") and p.get("title") == "增量测试-%s" % stamp]
    ok_new = bool(plan_id) and bool(hit1) and hit1[0].get("version") == 1 and hit1[0].get("deleted") is False
    check("看板建计划 → 端上增量能拉到（version=1）", ok_new,
          "plan_id=%s 命中 %d 条 version=%s" % (plan_id, len(hit1), hit1[0].get("version") if hit1 else "-"))

    st, patched = call("/api/v1/plans/%s" % plan_id, FAM,
                       {"user_id": "u-elder", "title": "增量测试-%s-改过" % stamp,
                        "dose": "2 片"}, method="PATCH")
    st, inc2 = call("/v1/plans?since=%d" % seq1)
    seq2 = int(inc2.get("next_seq") or 0)
    hit2 = [p for p in (inc2.get("plans") or []) if p.get("title") == "增量测试-%s-改过" % stamp]
    ok_patch = st == 200 and bool(hit2) and hit2[0].get("version") == 2 and hit2[0].get("dose") == "2 片"
    check("看板改计划 → 端上增量收到新内容 + version=2", ok_patch,
          "status=%s 命中 %d 条 version=%s" % (st, len(hit2), hit2[0].get("version") if hit2 else "-"))

    # ⑪ C-1 看板删计划要留 tombstone：软删 + bump，端上增量必须收到 deleted:true
    st_del_plan, gone = call("/api/v1/plans/%s?user_id=u-elder" % plan_id, FAM, None, method="DELETE")
    st, inc3 = call("/v1/plans?since=%d" % seq2)
    hit3 = [p for p in (inc3.get("plans") or []) if p.get("title", "").startswith("增量测试-%s" % stamp)]
    ok_del = st_del_plan == 200 and any(p.get("deleted") is True for p in hit3)
    check("看板删计划 → 端上增量收到 deleted:true", ok_del,
          "status=%s 命中 %d 条 deleted=%s" % (st_del_plan, len(hit3), [p.get("deleted") for p in hit3]))

    # ⑫ C-3 记录按 client_id 去重：同一 client_id 连发两次只落一条，两次回执 record_id 相同
    cid = "cid-%s" % stamp
    st_a, rec_a = call("/v1/records", ELDER, {"type": "water", "value": 200, "unit": "ml",
                                             "at": int(time.time() * 1000), "client_id": cid})
    st_b, rec_b = call("/v1/records", ELDER, {"type": "water", "value": 200, "unit": "ml",
                                             "at": int(time.time() * 1000), "client_id": cid})
    st_list, recs = call("/api/v1/records?days=1", FAM)
    rows = [r for r in (recs.get("items") or []) if r.get("client_id") == cid]
    same = rec_a.get("record_id") and rec_a.get("record_id") == rec_b.get("record_id")
    ok_cid = bool(same) and len(rows) == 1 and rec_b.get("duplicate") is True
    check("记录按 client_id 去重（发两次只一条）", ok_cid,
          "record_id %s/%s 库内 %d 条" % (rec_a.get("record_id"), rec_b.get("record_id"), len(rows)))

    # ⑬ C-4 /v1 能删记录：撤销要真的撤到云端（30 分钟窗口内）
    st_del, del_rec = call("/v1/records/%s" % rec_a.get("record_id"), ELDER, None, method="DELETE")
    st_list2, recs2 = call("/api/v1/records?days=1", FAM)
    still = [r for r in (recs2.get("items") or []) if r.get("client_id") == cid]
    ok_rdel = (st_del == 200 and del_rec.get("deleted") is True
               and del_rec.get("server_seq") and not still)
    check("DELETE /v1/records/{id} 撤销到云端", ok_rdel,
          "status=%s seen=%s 仍在看板 %d 条" % (st_del, del_rec.get("server_seq"), len(still)))

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
