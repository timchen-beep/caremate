# -*- coding: utf-8 -*-
# 作用：颐伴手机端（Qt/QML，fspro7967/yiban_android_app）对接层：把 /v1/* 的冻结契约翻译到本服务的领域模型
"""颐伴手机端 v1.1 契约适配层。

背景
----
手机端仓库 `fspro7967/yiban_android_app`（Qt 6/QML + C++）冻结了 6 个 facade 和一套
HTTP 契约（`docs/端上接口规范_v1.1.md` §8，形状见 `docs/fixtures/*.json`）：

    POST /v1/pair            配对（6 位码）→ {token, device_id, cursor}
    POST /v1/events          上报事件（单条或批量）→ {accepted/…, server_seq}
    GET  /v1/plans?since=    增量拉计划 → {plans:[…], next_seq}
    GET  /v1/state?since=    增量拉状态 → {occurrences:[…], next_seq, server_time}
    POST /v1/alarm           呼救/告警（occurrence_id 可空）→ {sent, channel}
    POST/PATCH/DELETE /v1/plans/{id}   计划写
    POST/PATCH /v1/records             记录写

本模块只做**翻译**，不复制业务：状态迁移一律走 `transition()`，计划写入走 `save_plan()`，
记录走 `add_record()`。因此两套接口共用同一个真相来源，不会出现"端上看得到、看板看不到"。

映射规则（与手机端文档逐条对应）
------------------------------
1. ID：端上要 int64，本服务内部是字符串。用 `v1_map` 表做双向映射；plan 自增，
   occurrence 按端上冻结公式生成（planId*1e9 + julianDay%1e7*100 + 当天序号），
   这样端上自己算出的 occurrenceId 与我们下发的一致，冲突时可当幂等键。
2. 时间：端上全是毫秒 int64，本服务内部是 UTC ISO 字符串，这里双向转换。
3. 游标：端上要单调整数 `server_seq`。用 `v1_seq` 计数器 + `v1_rowseq` 记录每行最后写入的序号。
4. 状态名六态完全一致（pending/notified/snoozed/confirmed/missed/escalated），直接透传。
5. 动作名端上是 confirm/snooze/miss/escalate/undo，本服务是 confirmed/snoozed/missed/
   escalated/reopen，这里做词表转换。
6. 窗口与升级：端上 `window_min` / `escalate_after_min` 对应本服务的"多久判 missed"和
   "多久通知家属"，分别取 CONFIG 的 th3 / th1，保证两边结论一致。

契约版本对账：本模块按 app 组仓库的 `docs/端上接口规范_v1.1.md`（2026-11-06 冻结）实现，
形状以 `docs/fixtures/*.json` 为准；`server/test_v1.py` 用同四份 fixtures 的字段做断言。
"""

import json
import sqlite3
from datetime import datetime, timedelta, timezone

import server as S

# 端上动作名 → 本服务动作名
ACTION_MAP = {
    "confirm": "confirmed",
    "snooze": "snoozed",
    "miss": "missed",
    "missed": "missed",
    "notify": "notified",
    "notified": "notified",
    "escalate": "escalated",
    "escalated": "escalated",
    "undo": "undo",
    "reopen": "reopen",
}
# 端上 action 里由计划接口负责的，不在 /v1/events 里处理
PLAN_ACTIONS = ("create", "edit")


# ================================================================ 基础设施：序号与 ID 映射
# 函数 ensure_tables：建适配层自己的三张表（不动业务表）
def ensure_tables(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS v1_seq(k TEXT PRIMARY KEY, v INTEGER NOT NULL DEFAULT 0)")
    conn.execute("CREATE TABLE IF NOT EXISTS v1_map(kind TEXT NOT NULL, local_id TEXT NOT NULL,"
                 " int_id INTEGER NOT NULL, PRIMARY KEY(kind, local_id), UNIQUE(kind, int_id))")
    conn.execute("CREATE TABLE IF NOT EXISTS v1_rowseq(kind TEXT NOT NULL, local_id TEXT NOT NULL,"
                 " seq INTEGER NOT NULL, PRIMARY KEY(kind, local_id))")
    conn.execute("CREATE TABLE IF NOT EXISTS v1_version(kind TEXT NOT NULL, local_id TEXT NOT NULL,"
                 " version INTEGER NOT NULL DEFAULT 1, PRIMARY KEY(kind, local_id))")
    conn.execute("CREATE TABLE IF NOT EXISTS v1_events(event_id TEXT PRIMARY KEY, seq INTEGER NOT NULL)")
    conn.execute("INSERT OR IGNORE INTO v1_seq(k, v) VALUES ('seq', 0)")


# 函数 next_seq：取下一个单调序号（写操作调用一次）
def next_seq(conn):
    ensure_tables(conn)
    conn.execute("UPDATE v1_seq SET v = v + 1 WHERE k = 'seq'")
    return conn.execute("SELECT v FROM v1_seq WHERE k='seq'").fetchone()["v"]


# 函数 current_seq：当前序号（不递增）
def current_seq(conn):
    ensure_tables(conn)
    row = conn.execute("SELECT v FROM v1_seq WHERE k='seq'").fetchone()
    return int(row["v"]) if row else 0


# 函数 row_seq：某行的写入序号；没有就现分配一个（读路径也能做增量）
def row_seq(conn, kind, local_id, bump=False):
    ensure_tables(conn)
    row = conn.execute("SELECT seq FROM v1_rowseq WHERE kind=? AND local_id=?",
                       (kind, local_id)).fetchone()
    if row and not bump:
        return int(row["seq"])
    seq = next_seq(conn)
    conn.execute("INSERT INTO v1_rowseq(kind, local_id, seq) VALUES (?,?,?)"
                 " ON CONFLICT(kind, local_id) DO UPDATE SET seq=excluded.seq",
                 (kind, local_id, seq))
    return seq


# 函数 int_id：本地字符串 id → 端上 int64（不存在则分配）
def int_id(conn, kind, local_id):
    ensure_tables(conn)
    row = conn.execute("SELECT int_id FROM v1_map WHERE kind=? AND local_id=?",
                       (kind, local_id)).fetchone()
    if row:
        return int(row["int_id"])
    if kind == "plan":
        # plan 用自增，保证 occurrenceId 公式里的 planId 稳定且可读
        cur = conn.execute("SELECT COALESCE(MAX(int_id),0)+1 AS n FROM v1_map WHERE kind='plan'").fetchone()
        value = int(cur["n"])
        conn.execute("INSERT INTO v1_map(kind, local_id, int_id) VALUES ('plan',?,?)", (local_id, value))
        return value
    if kind == "record":
        cur = conn.execute("SELECT COALESCE(MAX(int_id),0)+1 AS n FROM v1_map WHERE kind='record'").fetchone()
        value = int(cur["n"])
        conn.execute("INSERT INTO v1_map(kind, local_id, int_id) VALUES ('record',?,?)", (local_id, value))
        return value
    raise ValueError("未知 id 类型：%s" % kind)


# 函数 local_id：端上 int64 → 本地字符串 id（plan/record 用；occurrence 另有公式）
def local_id(conn, kind, value):
    ensure_tables(conn)
    row = conn.execute("SELECT local_id FROM v1_map WHERE kind=? AND int_id=?",
                       (kind, int(value))).fetchone()
    return row["local_id"] if row else None


# 函数 occurrence_int_id：按端上冻结公式生成 occurrenceId
def occurrence_int_id(conn, plan_int, slot_local, seq_in_day):
    """occurrenceId = planId*1e9 + (julianDay%1e7)*100 + 当天第几个（0 起）。"""
    day = datetime.strptime(slot_local[:10], "%Y-%m-%d").date()
    julian = day.toordinal() + 1721425          # 与 QDate::toJulianDay 同口径
    return plan_int * 1000000000 + (julian % 10000000) * 100 + int(seq_in_day)


# ================================================================ 时间换算
# 函数 ms_of：ISO/墙钟字符串 → 毫秒时间戳
def ms_of(value):
    if value in (None, "", 0):
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    dt = S.parse_iso(str(value))
    if dt is None:
        try:
            dt = datetime.strptime(str(value), "%Y-%m-%d %H:%M").replace(tzinfo=S.tzinfo())
        except ValueError:
            return 0
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=S.tzinfo())
    return int(dt.timestamp() * 1000)


# 函数 iso_of_ms：毫秒时间戳 → UTC ISO（本服务内部存储格式）
def iso_of_ms(ms):
    if not ms:
        return ""
    return S.iso(datetime.fromtimestamp(int(ms) / 1000.0, tz=timezone.utc))


# ================================================================ 视图：本服务行 → 端上形状
# 函数 plan_payload：plans 表行 → 端上 plan（§3.2 + plans_since.json）
def plan_payload(conn, row):
    row = dict(row)
    try:
        rule = json.loads(row.get("rule") or "{}")
    except ValueError:
        rule = {}
    if not isinstance(rule, dict) or not rule:
        rule = {"kind": "daily"}
    kind = rule.get("kind") or "daily"
    if kind not in ("daily", "weekly", "monthly", "once"):
        # 本服务支持的复杂规则（interval/course/meal_offset）降级成 daily + times，
        # 端上只认四种；具体时刻已由 times 表达，行为不丢。
        rule = {"kind": "daily", "times": list(rule.get("times") or [])}
    times = rule.get("times") or [t for t in (row.get("times") or "").split(",") if t]
    if kind != "once" and times:
        rule["times"] = times
    ver = conn.execute("SELECT version FROM v1_version WHERE kind='plan' AND local_id=?",
                       (row["id"],)).fetchone()
    return {
        "plan_id": int_id(conn, "plan", row["id"]),
        "title": row.get("title", ""),
        "dose": row.get("dose", ""),
        "note": row.get("note", ""),
        "rule": rule,
        "window_min": int(S.CONFIG["th3"]),
        "escalate_after_min": int(S.CONFIG["th1"]),
        "version": int(ver["version"]) if ver else 1,
        "deleted": not bool(row.get("active", 1)),
        "updated_seq": row_seq(conn, "plan", row["id"]),
    }


# 函数 occurrence_payload：occurrences 行 → 端上 occurrence（§3.1 + state_since.json）
def occurrence_payload(conn, row, plan_row=None):
    row = dict(row)
    plan_row = plan_row or conn.execute("SELECT * FROM plans WHERE id=?", (row["plan_id"],)).fetchone()
    plan = dict(plan_row) if plan_row else {}
    plan_int = int_id(conn, "plan", row["plan_id"])
    slot = row.get("slot_local") or S.local_str(row["due_at"])
    # 当天第几个提醒：数"同日同计划、到期更早"的实例数——与规则类型无关，
    # 比按 times 下标推更稳（interval/course 这类规则的 times 不等于当天实际时刻）。
    early = conn.execute(
        "SELECT COUNT(*) AS c FROM occurrences WHERE plan_id=? AND user_id=?"
        " AND substr(due_at,1,10)=? AND due_at<?",
        (row["plan_id"], row.get("user_id", ""), row["due_at"][:10], row["due_at"])).fetchone()
    seq_in_day = int(early["c"]) if early else 0
    oid = occurrence_int_id(conn, plan_int, slot, seq_in_day)
    snooze_until = 0
    if row.get("state") == "snoozed":
        snooze_until = ms_of(row.get("updated_at")) + int(S.CONFIG["snooze_gap"]) * 60 * 1000
    last = conn.execute("SELECT seq FROM v1_rowseq WHERE kind='occurrence' AND local_id=?",
                        (row["id"],)).fetchone()
    return {
        "occurrence_id": oid,
        "plan_id": plan_int,
        "title": row.get("title_snap") or plan.get("title", row.get("plan_id", "")),
        "dose": row.get("dose_snap") or plan.get("dose", ""),
        "note": plan.get("note", ""),
        "due_ts": ms_of(row["due_at"]),
        "state": row["state"],
        "snooze_count": int(row.get("snooze_count") or 0),
        "snooze_until_ts": snooze_until,
        "window_min": int(S.CONFIG["th3"]),
        "escalate_after_min": int(S.CONFIG["th1"]),
        "updated_seq": int(last["seq"]) if last else row_seq(conn, "occurrence", row["id"]),
        "last_event_id": _last_event_id(conn, row["id"]),
    }


# 函数 _last_event_id：该实例最后一条事件的 id（端上用来判重放）
def _last_event_id(conn, oid):
    row = conn.execute("SELECT event_id FROM events WHERE occurrence_id=? ORDER BY created_at DESC LIMIT 1",
                       (oid,)).fetchone()
    return (row["event_id"] if row else "") or ""


# 函数 _ensure_row_seq：取某行序号；没有则分配一个（保证 since=0 时能拿到全量）
def _ensure_row_seq(conn, kind, local_id):
    ensure_tables(conn)
    row = conn.execute("SELECT seq FROM v1_rowseq WHERE kind=? AND local_id=?",
                       (kind, local_id)).fetchone()
    if row:
        return int(row["seq"])
    return row_seq(conn, kind, local_id, bump=True)


# ================================================================ 入口：GET
# 函数 handle_get：处理 /v1/* 的 GET（返回 True 表示已处理）
def handle_get(handler, path, query):
    if not path.startswith("/v1/"):
        return False
    user = handler.me()
    if not user:
        handler.json(401, {"error": "auth", "detail": "令牌无效"})
        return True
    elder = user.get("paired_elder") or user["id"]
    since = int(query.get("since") or 0)

    if path == "/v1/state":
        today = S.utc_now().astimezone(S.tzinfo()).date()
        with S.connect() as conn:
            ensure_tables(conn)
            # 实例是按需物化的：不先物化，端上永远拉不到今天的提醒
            S.ensure_occurrences(elder, today - timedelta(days=1), today + timedelta(days=1), conn)
            rows = conn.execute("SELECT * FROM occurrences WHERE user_id=? ORDER BY due_at LIMIT 800",
                                (elder,)).fetchall()
            picked = []
            for r in rows:
                seq_of_row = _ensure_row_seq(conn, "occurrence", r["id"])
                if seq_of_row > since:
                    picked.append((seq_of_row, r))
            payload = [occurrence_payload(conn, r) for _, r in picked]
            conn.commit()
            seq = current_seq(conn)
        handler.json(200, {"occurrences": payload, "next_seq": seq,
                           "server_time": int(S.utc_now().timestamp() * 1000)})
        return True

    if path == "/v1/plans":
        with S.connect() as conn:
            ensure_tables(conn)
            rows = conn.execute("SELECT * FROM plans WHERE user_id=? ORDER BY id", (elder,)).fetchall()
            picked = [(seq, r) for seq, r in
                      ((_ensure_row_seq(conn, "plan", r["id"]), r) for r in rows) if seq > since]
            payload = [plan_payload(conn, r) for _, r in picked]
            conn.commit()
            seq = current_seq(conn)
        handler.json(200, {"plans": payload, "next_seq": seq})
        return True

    if path in ("/v1/health", "/v1/ping"):
        handler.json(200, {"ok": True, "version": S.VERSION,
                           "server_time": int(S.utc_now().timestamp() * 1000)})
        return True

    handler.json(404, {"error": "bad_request", "detail": "no route: %s" % path})
    return True


# ================================================================ 入口：POST / PATCH / DELETE
# 函数 handle_body：处理 /v1/* 的写请求（body 由调用方解析好传入，避免二次读 rfile）
def handle_body(handler, path, body, method):
    if not path.startswith("/v1/"):
        return False
    body = body or {}
    user = handler.me()
    if not user:
        handler.json(401, {"error": "auth", "detail": "令牌无效"})
        return True
    elder = user.get("paired_elder") or user["id"]

    if path == "/v1/pair" and method == "POST":
        return _pair(handler, body)

    if path == "/v1/events" and method == "POST":
        return _events(handler, body, elder)

    if path == "/v1/alarm" and method == "POST":
        return _alarm(handler, body, elder)

    if path == "/v1/plans" and method == "POST":
        return _plan_write(handler, body, elder, None, "POST")

    if path.startswith("/v1/plans/"):
        return _plan_write(handler, body, elder, path.rsplit("/", 1)[-1], method)

    if path == "/v1/records" and method == "POST":
        return _record_write(handler, body, elder, None, "POST")

    if path.startswith("/v1/records/"):
        return _record_write(handler, body, elder, path.rsplit("/", 1)[-1], method)

    handler.json(404, {"error": "bad_request", "detail": "no route: %s" % path})
    return True


# 函数 _pair：6 位配对码 → 令牌（复用 users.bind_code 与 sessions 表）
def _pair(handler, body):
    import secrets as _secrets
    code = str(body.get("pair_code") or body.get("pairing_code") or "").strip()
    device = str(body.get("device_id") or "android-unknown")[:64]
    with S.connect() as conn:
        ensure_tables(conn)
        row = conn.execute("SELECT * FROM users WHERE bind_code=? AND role='elder'",
                           (code,)).fetchone()
        if not row:
            handler.json(404, {"error": "pair_code_not_found", "detail": "配对码不存在"})
            return True
        token = "ses-" + _secrets.token_urlsafe(24)
        expires = S.iso(S.utc_now() + timedelta(days=30))
        conn.execute("INSERT INTO sessions (token,user_id,elder_id,label,created_at,expires_at)"
                     " VALUES (?,?,?,?,?,?)",
                     (token, "u-family", row["id"], device, S.iso(S.utc_now()), expires))
        conn.commit()
        cursor = current_seq(conn)
    handler.json(200, {"token": token, "device_id": device, "cursor": cursor,
                       "elder_id": row["id"], "elder_name": row["name"]})
    return True


# 函数 _events：上报事件（单条或批量），去重 + 走 transition()
def _events(handler, body, elder):
    items = body.get("events") if isinstance(body, dict) and isinstance(body.get("events"), list) else [body]
    batch = isinstance(body.get("events"), list)
    accepted, rejected = [], []
    for idx, item in enumerate(items):
        item = item or {}
        event_id = str(item.get("event_id") or "")
        action = ACTION_MAP.get(str(item.get("action") or "").lower())
        oid_int = item.get("occurrence_id")
        with S.connect() as conn:
            ensure_tables(conn)
            dup = conn.execute("SELECT seq FROM v1_events WHERE event_id=?", (event_id,)).fetchone()
            if dup:
                conn.commit()
                accepted.append({"event_id": event_id, "server_seq": int(dup["seq"]), "applied": False})
                continue
            oid = _resolve_occurrence(conn, oid_int)
        if not action:
            rejected.append({"index": idx, "event_id": event_id,
                             "code": "bad_request", "detail": "action 不在契约内"})
            continue
        if str(item.get("action") or "").lower() in PLAN_ACTIONS:
            rejected.append({"index": idx, "event_id": event_id,
                             "code": "bad_request", "detail": "create/edit 走 /v1/plans"})
            continue
        if not oid:
            rejected.append({"index": idx, "event_id": event_id,
                             "code": "occurrence_not_found", "detail": "找不到该提醒"})
            continue
        try:
            S.transition(oid, action, actor=elder, source="app-sync",
                         client_ts=iso_of_ms(item.get("ts")) or S.iso(S.utc_now()),
                         payload={"event_id": event_id, "note": item.get("reason", "")})
        except (ChildProcessError, TimeoutError) as exc:
            with S.connect() as conn:
                ensure_tables(conn)
                st = conn.execute("SELECT state FROM occurrences WHERE id=?", (oid,)).fetchone()
                seq = current_seq(conn)
            handler.json(409, {"error": {"code": "state_conflict", "message": str(exc),
                                         "occurrence_id": int(oid_int or 0),
                                         "server_state": st["state"] if st else "",
                                         "server_seq": seq}})
            return True
        except LookupError as exc:
            rejected.append({"index": idx, "event_id": event_id,
                             "code": "occurrence_not_found", "detail": str(exc)})
            continue
        with S.connect() as conn:
            ensure_tables(conn)
            seq = next_seq(conn)
            conn.execute("INSERT OR IGNORE INTO v1_events(event_id, seq) VALUES (?,?)", (event_id, seq))
            conn.execute("INSERT INTO v1_rowseq(kind, local_id, seq) VALUES ('occurrence',?,?)"
                         " ON CONFLICT(kind, local_id) DO UPDATE SET seq=excluded.seq", (oid, seq))
            conn.commit()
        accepted.append({"event_id": event_id, "server_seq": seq, "applied": True})

    if batch:
        handler.json(200, {"accepted": accepted, "rejected": rejected,
                           "next_seq": accepted[-1]["server_seq"] if accepted else 0})
    else:
        first = accepted[0] if accepted else None
        if first and first["applied"]:
            handler.json(201, {"accepted": True, "server_seq": first["server_seq"]})
        elif first:
            handler.json(200, {"accepted": False, "dedup": True, "server_seq": first["server_seq"]})
        else:
            handler.json(400, {"error": rejected[0]["code"] if rejected else "bad_request",
                               "detail": rejected[0]["detail"] if rejected else ""})
    return True


# 函数 _resolve_occurrence：端上 int64 occurrenceId → 本地 occurrence id
def _resolve_occurrence(conn, oid_int):
    if oid_int in (None, "", 0):
        return None
    target = int(oid_int)
    # 先按端上公式直接反推：planId = oid // 1e9，然后按日期+序号匹配
    plan_int = target // 1000000000
    plan_local = local_id(conn, "plan", plan_int)
    if plan_local:
        for row in conn.execute("SELECT id, plan_id, slot_local, due_at FROM occurrences"
                                " WHERE plan_id=?", (plan_local,)).fetchall():
            local_plan_int = int_id(conn, "plan", row["plan_id"])
            slot = row["slot_local"] or S.local_str(row["due_at"])
            for seq_in_day in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9):
                if occurrence_int_id(conn, local_plan_int, slot, seq_in_day) == target:
                    return row["id"]
    return None


# 函数 _alarm：呼救/告警（occurrence_id 可空，source=manual）
def _alarm(handler, body, elder):
    level = int(body.get("level") or 1)
    reason = str(body.get("reason") or "")
    device = str(body.get("device_id") or "")
    oid_int = body.get("occurrence_id")
    with S.connect() as conn:
        ensure_tables(conn)
        oid = _resolve_occurrence(conn, oid_int)
        seq = next_seq(conn)
        conn.commit()
    if level >= 3 or str(body.get("source") or "") == "manual" or not oid:
        S.sos(elder, elder, note=reason or "端上呼救", device=device)
    else:
        S.raise_alarm(elder, "escalated", level, oid, reason or "未确认")
    handler.json(200, {"sent": True, "channel": "webhook", "server_seq": seq})
    return True


# 函数 _plan_write：计划的 POST / PATCH / DELETE（rule 四种 → 本服务 times/weekdays/rule）
def _plan_write(handler, body, elder, plan_int, method):
    with S.connect() as conn:
        ensure_tables(conn)
        local = local_id(conn, "plan", plan_int) if plan_int else None
    if method == "DELETE":
        if not local:
            handler.json(404, {"error": "plan_not_found", "detail": "计划不存在"})
            return True
        S.save_plan(elder, {"active": 0}, plan_id=local)
        with S.connect() as conn:
            ensure_tables(conn)
            conn.execute("UPDATE v1_version SET version=version+1 WHERE kind='plan' AND local_id=?",
                         (local,))
            conn.commit()
            row = conn.execute("SELECT * FROM plans WHERE id=?", (local,)).fetchone()
            payload = plan_payload(conn, row)
            conn.commit()
        handler.json(200, payload)
        return True

    if method == "PATCH" and not local:
        handler.json(404, {"error": "plan_not_found", "detail": "计划不存在"})
        return True

    rule = body.get("rule") or {}
    if isinstance(rule, str):
        try:
            rule = json.loads(rule)
        except ValueError:
            rule = {}
    merged = {
        "title": body.get("title"),
        "dose": body.get("dose", ""),
        "note": body.get("note", ""),
        "times": rule.get("times") or [],
        "weekdays": rule.get("weekdays") or [],
        "rule": rule,
    }
    if method == "PATCH" and local:
        with S.connect() as conn:
            cur = conn.execute("SELECT * FROM plans WHERE id=?", (local,)).fetchone()
        for key in ("title", "dose", "note"):
            if body.get(key) is None:
                merged[key] = cur[key]
        if not merged["times"]:
            merged["times"] = [t for t in (cur["times"] or "").split(",") if t]
        if not merged["weekdays"]:
            merged["weekdays"] = [int(d) for d in (cur["weekdays"] or "").split(",") if d]
        if not body.get("rule"):
            merged["rule"] = json.loads(cur["rule"] or "{}") or {"kind": "daily"}
    try:
        res = S.save_plan(elder, merged, plan_id=local)
    except (KeyError, ValueError) as exc:
        handler.json(422, {"error": "bad_request", "detail": "参数不合法：%s" % exc})
        return True
    pid = (res or {}).get("id") or local
    with S.connect() as conn:
        ensure_tables(conn)
        conn.execute("INSERT INTO v1_version(kind, local_id, version) VALUES ('plan',?,1)"
                     " ON CONFLICT(kind, local_id) DO UPDATE SET version=version+1", (pid,))
        conn.commit()
        row = conn.execute("SELECT * FROM plans WHERE id=?", (pid,)).fetchone()
        payload = plan_payload(conn, row)
        conn.commit()
    handler.json(201 if method == "POST" else 200, payload)
    return True


# 函数 _record_write：记录的 POST / PATCH（at 毫秒 → occurred_at 墙钟）
def _record_write(handler, body, elder, record_int, method):
    with S.connect() as conn:
        ensure_tables(conn)
        local = local_id(conn, "record", record_int) if record_int else None
    if method == "PATCH":
        if not local:
            handler.json(404, {"error": "record_not_found", "detail": "记录不存在"})
            return True
        try:
            S.correct_record(local, {"value": body.get("value"),
                                     "unit": body.get("unit"),
                                     "note": body.get("note", "")}, elder)
        except ValueError as exc:
            handler.json(422, {"error": "bad_request", "detail": str(exc)})
            return True
    else:
        payload = {
            "type": body.get("type"),
            "value": body.get("value"),
            "unit": body.get("unit"),
            "occurred_at": iso_of_ms(body.get("at")) or None,
            "note": body.get("note", ""),
        }
        try:
            res = S.add_record(elder, payload, elder)
        except ValueError as exc:
            handler.json(422, {"error": "bad_request", "detail": str(exc)})
            return True
        local = res["id"]
    with S.connect() as conn:
        ensure_tables(conn)
        seq = next_seq(conn)
        rid = int_id(conn, "record", local)
        conn.execute("INSERT INTO v1_rowseq(kind, local_id, seq) VALUES ('record',?,?)"
                     " ON CONFLICT(kind, local_id) DO UPDATE SET seq=excluded.seq", (local, seq))
        conn.commit()
    handler.json(201 if method == "POST" else 200,
                 {"record_id": rid, "corrected_from": int(record_int or 0), "server_seq": seq})
    return True
