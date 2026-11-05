# -*- coding: utf-8 -*-
"""CareMate 云端 v0.5 —— 按《Opening Report 4.2》对齐的实现。

对齐的六条（文档 4.2.3–4.2.6）：
1) occurrence 落表，状态持久化（pending / notified / snoozed / confirmed / missed / escalated）
2) 调度器在服务进程内，每 30 s 扫一次到期实例；升级链 2/5/15 min 由 job 产生，不依赖任何页面
3) 唯一状态入口 transition(occ, action, actor, now)；任何接口都不直接写 state 列
4) 幂等：occurrence.id = uuid5(plan_id + due_at)；event_id = uuid5(occurrence_id, action, client_ts)，唯一索引
5) 时间统一 UTC 存储（带 Z），另有 tz 字段用于本地展示
6) event 记 actor；记录更正是追加式（superseded_by），永不覆盖

保留：plans / records / alarms / outbox（MQTT 出口）/ 三角色 / CSV 导出 / App bundle 兼容接口。

运行： python server.py --port 8000
"""

import argparse
import csv
import io
import json
import os
import re
import secrets
import shutil
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import urllib.request
from urllib.parse import parse_qs, urlparse

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

VERSION = "1.0.0"
TICK = 30  # 调度器扫描间隔（秒），文档 4.2.3

BASE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
if not os.path.isdir(os.path.join(BASE, "web")) and os.path.isdir(os.path.join(os.getcwd(), "web")):
    BASE = os.getcwd()
WEB = os.path.join(BASE, "web")

CONFIG = {
    "db": os.environ.get("CAREMATE_DB", os.path.join(BASE, "caremate.db")),
    "tz": os.environ.get("CAREMATE_TZ", "Asia/Shanghai"),
    "mode": os.environ.get("CAREMATE_MODE", "local"),
    "jwt_secret": os.environ.get("CAREMATE_JWT_SECRET", ""),
    "mqtt_url": os.environ.get("CAREMATE_MQTT_URL", ""),
    "webhook_url": os.environ.get("CAREMATE_WEBHOOK_URL", ""),
    "th1": int(os.environ.get("CAREMATE_THRESHOLD_1", "2")),
    "th2": int(os.environ.get("CAREMATE_THRESHOLD_2", "5")),
    "th3": int(os.environ.get("CAREMATE_THRESHOLD_3", "15")),
    "snooze_max": 3,
    # 第 5 步：确认后 5 秒内允许撤销（演示要求「要紧的操作后面跟一个 5 秒撤销条」）
    "undo_seconds": int(os.environ.get("CAREMATE_UNDO_SECONDS", "5")),
    # 第 4 步：记录撤销窗口 30 分钟
    "record_undo_minutes": int(os.environ.get("CAREMATE_RECORD_UNDO_MINUTES", "30")),
    # 第 6 步：多久没动静算异常（小时）
    "inactivity_hours": float(os.environ.get("CAREMATE_INACTIVITY_HOURS", "2")),
    # 文档第 2 步：点「等会儿」→ 五分钟后再说一遍
    "snooze_gap": int(os.environ.get("CAREMATE_SNOOZE_GAP", "5")),
    "scheduler": os.environ.get("CAREMATE_SCHEDULER", "1") != "0",
    # 磁盘水位：剩余空间低于此值就拒绝写入（文档 4.2.6）
    "disk_min_mb": int(os.environ.get("CAREMATE_DISK_MIN_MB", "200")),
    # 配对码限速：每地址每分钟最多 5 次（文档 4.2.7）
    "pair_per_min": int(os.environ.get("CAREMATE_PAIR_PER_MIN", "5")),
}
DB_PATH = CONFIG["db"]
_lock = threading.RLock()

STATES = ("pending", "notified", "snoozed", "confirmed", "missed", "escalated")


# ================================================================ 时间（UTC 存、tz 显示）
def tzinfo():
    if ZoneInfo:
        try:
            return ZoneInfo(CONFIG["tz"])
        except Exception:
            pass
    return timezone(timedelta(hours=8))


def utc_now():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(s):
    if not s:
        return None
    s = str(s).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def local_dt(iso_s):
    dt = parse_iso(iso_s)
    return dt.astimezone(tzinfo()) if dt else None


def local_str(iso_s, fmt="%Y-%m-%d %H:%M"):
    dt = local_dt(iso_s)
    return dt.strftime(fmt) if dt else ""


def minutes_since(iso_s, now=None):
    dt = parse_iso(iso_s)
    if not dt:
        return 0
    return ((now or utc_now()) - dt).total_seconds() / 60.0


# ================================================================ 输入格式化（容错）
def normalize_times(raw):
    """接受 "08:00"、"8点"、"0800"，也接受契约里的 ISO 时间 "2026-11-05T08:00:00+08:00"。"""
    items = raw if isinstance(raw, (list, tuple)) else str(raw or "").replace("，", ",").split(",")
    out = []
    for item in items:
        t = str(item).strip()
        if not t:
            continue
        if "T" in t:                      # ISO 8601：取本地墙钟部分
            t = t.split("T", 1)[1][:5]
        m = re.match(r"^(\d{1,2})\s*[:：.点]\s*(\d{1,2})$", t) or re.match(r"^(\d{1,2})(\d{2})$", t)
        if not m:
            continue
        h, mi = int(m.group(1)), int(m.group(2))
        if h > 23 or mi > 59:
            continue
        v = "%02d:%02d" % (h, mi)
        if v not in out:
            out.append(v)
    return sorted(out)


def normalize_weekdays(raw):
    items = raw if isinstance(raw, (list, tuple)) else str(raw or "").replace("，", ",").split(",")
    days = set()
    for d in items:
        try:
            n = int(str(d).strip())
        except (TypeError, ValueError):
            continue
        if 1 <= n <= 7:
            days.add(n)
    return sorted(days) or [1, 2, 3, 4, 5, 6, 7]


# ================================================================ 数据库
SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL,
    token TEXT NOT NULL UNIQUE, bind_code TEXT, tz TEXT NOT NULL DEFAULT 'Asia/Shanghai',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS links (
    family_id TEXT NOT NULL, elder_id TEXT NOT NULL,
    can_edit INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL,
    PRIMARY KEY (family_id, elder_id)
);
CREATE TABLE IF NOT EXISTS plans (
    id TEXT PRIMARY KEY, user_id TEXT NOT NULL, title TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'medication', times TEXT NOT NULL DEFAULT '',
    weekdays TEXT NOT NULL DEFAULT '1,2,3,4,5,6,7', rule TEXT NOT NULL DEFAULT '',
    dose TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '',
    paused_until TEXT NOT NULL DEFAULT '', active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS occurrences (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL, plan_id TEXT NOT NULL,
    slot_local TEXT NOT NULL DEFAULT '',      -- 本地墙钟 YYYY-MM-DD HH:MM，实例的稳定身份
    due_at TEXT NOT NULL,                     -- 该墙钟在写入时时区下的 UTC 时刻
    title_snap TEXT NOT NULL DEFAULT '',      -- 物化时的计划快照：改计划不改历史
    dose_snap TEXT NOT NULL DEFAULT '',
    kind_snap TEXT NOT NULL DEFAULT '',
    state TEXT NOT NULL DEFAULT 'pending',
    level INTEGER NOT NULL DEFAULT 0,
    snooze_count INTEGER NOT NULL DEFAULT 0,
    notified_at TEXT NOT NULL DEFAULT '',
    confirmed_at TEXT NOT NULL DEFAULT '',
    missed_at TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL,
    UNIQUE (plan_id, due_at)
);
CREATE INDEX IF NOT EXISTS idx_occ_due ON occurrences (user_id, due_at);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    occurrence_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    action TEXT NOT NULL,
    actor TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'app',
    payload TEXT NOT NULL DEFAULT '{}',
    at_utc TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ev_occ ON events (occurrence_id);
CREATE TABLE IF NOT EXISTS records (
    id TEXT PRIMARY KEY, user_id TEXT NOT NULL, type TEXT NOT NULL,
    value REAL, unit TEXT NOT NULL DEFAULT '', occurred_at TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '', created_by TEXT NOT NULL DEFAULT '',
    updated_by TEXT NOT NULL DEFAULT '', revision INTEGER NOT NULL DEFAULT 1,
    superseded_by TEXT NOT NULL DEFAULT '', deleted INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS alarms (
    id TEXT PRIMARY KEY, user_id TEXT NOT NULL, kind TEXT NOT NULL,
    level INTEGER NOT NULL DEFAULT 1, occurrence TEXT NOT NULL DEFAULT '',
    message TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL,
    acked_at TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT, topic TEXT NOT NULL,
    payload TEXT NOT NULL, created_at TEXT NOT NULL, delivered_at TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY, user_id TEXT NOT NULL, elder_id TEXT NOT NULL,
    label TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT NOT NULL);
"""


def connect():
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def migrate(conn):
    """老库补列/补表；历史时间字段一次性转 UTC。"""
    def cols(table):
        return {r["name"] for r in conn.execute("PRAGMA table_info(%s)" % table)}

    pcols = cols("plans")
    for name, ddl in (("rule", "TEXT NOT NULL DEFAULT ''"), ("dose", "TEXT NOT NULL DEFAULT ''"),
                      ("note", "TEXT NOT NULL DEFAULT ''"), ("paused_until", "TEXT NOT NULL DEFAULT ''"),
                      ("created_at", "TEXT NOT NULL DEFAULT ''")):
        if name not in pcols:
            conn.execute("ALTER TABLE plans ADD COLUMN %s %s" % (name, ddl))
    conn.execute("UPDATE plans SET created_at=updated_at WHERE created_at=''")

    if "tz" not in cols("users"):
        conn.execute("ALTER TABLE users ADD COLUMN tz TEXT NOT NULL DEFAULT 'Asia/Shanghai'")
    if "superseded_by" not in cols("records"):
        conn.execute("ALTER TABLE records ADD COLUMN superseded_by TEXT NOT NULL DEFAULT ''")
    if "created_at" not in cols("occurrences"):
        conn.execute("ALTER TABLE occurrences ADD COLUMN created_at TEXT NOT NULL DEFAULT ''")
        conn.execute("UPDATE occurrences SET created_at=updated_at WHERE created_at=''")
    ocols = cols("occurrences")
    for name, ddl in (("slot_local", "TEXT NOT NULL DEFAULT ''"),
                      ("title_snap", "TEXT NOT NULL DEFAULT ''"),
                      ("dose_snap", "TEXT NOT NULL DEFAULT ''"),
                      ("kind_snap", "TEXT NOT NULL DEFAULT ''")):
        if name not in ocols:
            conn.execute("ALTER TABLE occurrences ADD COLUMN %s %s" % (name, ddl))
    # 回填 slot_local（老行按 due_at 还原成本地墙钟），并把快照补上
    for r in conn.execute("SELECT * FROM occurrences WHERE slot_local=''").fetchall():
        slot = local_str(r["due_at"], "%Y-%m-%d %H:%M")
        plan = conn.execute("SELECT title,dose,kind FROM plans WHERE id=?", (r["plan_id"],)).fetchone()
        conn.execute("UPDATE occurrences SET slot_local=?,title_snap=?,dose_snap=?,kind_snap=? WHERE id=?",
                     (slot, (plan["title"] if plan else ""), (plan["dose"] if plan else ""),
                      (plan["kind"] if plan else ""), r["id"]))
    # 同一 (plan_id, slot_local) 可能有历史重复（换时区跑过），保留状态最靠后的那条
    dups = conn.execute(
        "SELECT plan_id, slot_local, COUNT(*) c FROM occurrences GROUP BY plan_id, slot_local"
        " HAVING c > 1").fetchall()
    for d in dups:
        rows = conn.execute(
            "SELECT id FROM occurrences WHERE plan_id=? AND slot_local=?"
            " ORDER BY CASE state WHEN 'confirmed' THEN 0 WHEN 'missed' THEN 1 ELSE 2 END, updated_at",
            (d["plan_id"], d["slot_local"])).fetchall()
        for extra in rows[1:]:
            conn.execute("DELETE FROM occurrences WHERE id=?", (extra["id"],))
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_occ_slot ON occurrences (plan_id, slot_local)")

    done = conn.execute("SELECT v FROM meta WHERE k='utc_migrated'").fetchone()
    if not done:
        for r in conn.execute("SELECT id, created_at FROM events WHERE created_at NOT LIKE '%Z%'").fetchall():
            dt = None
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
                try:
                    dt = datetime.strptime(r["created_at"], fmt).replace(tzinfo=tzinfo())
                    break
                except ValueError:
                    continue
            if dt:
                conn.execute("UPDATE events SET created_at=?, at_utc=? WHERE id=?",
                             (iso(dt), iso(dt), r["id"]))
        conn.execute("INSERT OR REPLACE INTO meta (k,v) VALUES ('utc_migrated', ?)", (iso(utc_now()),))

    for row in conn.execute("SELECT id,times,weekdays FROM plans").fetchall():
        nt = ",".join(normalize_times(row["times"]))
        nw = ",".join(str(x) for x in normalize_weekdays(row["weekdays"]))
        if nt != row["times"] or nw != row["weekdays"]:
            conn.execute("UPDATE plans SET times=?,weekdays=?,active=? WHERE id=?",
                         (nt, nw, 1 if nt else 0, row["id"]))


def init_db():
    with connect() as conn:
        conn.executescript(SCHEMA)
        migrate(conn)
        if conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]:
            return
        t = iso(utc_now())
        conn.executemany(
            "INSERT INTO users (id,name,role,token,bind_code,tz,created_at) VALUES (?,?,?,?,?,?,?)",
            [("u-elder", "张阿姨", "elder", "app-elder-001", "8823", CONFIG["tz"], t),
             ("u-family", "家属（女儿）", "family", "fam-demo-2026", None, CONFIG["tz"], t),
             ("u-community", "社区网格员", "community", "comm-demo-2026", None, CONFIG["tz"], t)],
        )
        conn.execute("INSERT INTO links (family_id,elder_id,can_edit,created_at) VALUES (?,?,?,?)",
                     ("u-family", "u-elder", 1, t))
        conn.execute("INSERT INTO links (family_id,elder_id,can_edit,created_at) VALUES (?,?,?,?)",
                     ("u-community", "u-elder", 0, t))
        conn.executemany(
            "INSERT INTO plans (id,user_id,title,kind,times,weekdays,rule,dose,note,active,created_at,updated_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            [("p-amlodipine", "u-elder", "苯磺酸氨氯地平 5mg", "medication", "08:00,20:00",
              "1,2,3,4,5,6,7", json.dumps({"kind": "daily"}), "1 片", "餐后", 1, t, t),
             ("p-metformin", "u-elder", "二甲双胍 0.5g", "medication", "12:30",
              "1,2,3,4,5,6,7", json.dumps({"kind": "mealOffset", "anchor": "lunch", "offset": 30}),
              "1 片", "随餐", 1, t, t),
             ("p-water", "u-elder", "喝水 200ml", "water", "10:00,15:30",
              "1,2,3,4,5,6,7", json.dumps({"kind": "daily"}), "200 ml", "", 1, t, t)],
        )


# ================================================================ 账号与权限
def user_by_token(token):
    """先认演示账号的固定令牌，再认配对码换来的会话令牌（文档：token 是唯一凭据）。"""
    if not token:
        return None
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE token=?", (token,)).fetchone()
        if row:
            return dict(row)
        ses = conn.execute("SELECT * FROM sessions WHERE token=?", (token,)).fetchone()
        if not ses:
            return None
        if parse_iso(ses["expires_at"]) and parse_iso(ses["expires_at"]) < utc_now():
            return None
        owner = conn.execute("SELECT * FROM users WHERE id=?", (ses["user_id"],)).fetchone()
    user = dict(owner) if owner else {"id": ses["user_id"], "name": "照护者", "role": "family",
                                      "bind_code": None, "tz": CONFIG["tz"]}
    user["token"] = token
    user["paired_elder"] = ses["elder_id"]
    user["session"] = True
    return user


def link_of(viewer_id, elder_id):
    if viewer_id == elder_id:
        return {"can_edit": 1, "self": True}
    with connect() as conn:
        row = conn.execute("SELECT * FROM links WHERE family_id=? AND elder_id=?",
                           (viewer_id, elder_id)).fetchone()
    return dict(row) if row else None


def can_view(user, target):
    """会话令牌只能看自己配对的老人；演示账号按 links 表判定。"""
    if user.get("paired_elder"):
        return {"can_edit": 1, "from_session": True} if user["paired_elder"] == target else None
    return link_of(user["id"], target)


# ================================================================ 规则展开（七种）
def rule_of(plan):
    raw = plan["rule"] if isinstance(plan, dict) else plan["rule"]
    if raw:
        try:
            return json.loads(raw)
        except ValueError:
            pass
    wd = plan["weekdays"] if isinstance(plan, dict) else plan["weekdays"]
    return {"kind": "weekly" if wd != "1,2,3,4,5,6,7" else "daily"}


def plan_times(plan):
    return normalize_times(plan["times"])


def slots_on(plan, day):
    rule = rule_of(plan)
    kind = rule.get("kind", "daily")
    times = plan_times(plan)
    paused = plan["paused_until"] or ""
    if paused and day.isoformat() <= paused[:10]:
        return []
    if kind == "weekly":
        return times if day.isoweekday() in normalize_weekdays(plan["weekdays"]) else []
    if kind == "interval":
        start = (rule.get("start") or "")[:10]
        n = max(1, int(rule.get("n", 2)))
        if not start:
            return times
        try:
            s = datetime.strptime(start, "%Y-%m-%d").date()
        except ValueError:
            return times
        return times if (day - s).days % n == 0 else []
    if kind == "monthly":
        return times if day.day == int(rule.get("day", 1)) else []
    if kind == "course":
        start = (rule.get("start") or "")[:10]
        days = int(rule.get("days", 7))
        try:
            s = datetime.strptime(start, "%Y-%m-%d").date()
        except ValueError:
            return times
        return times if 0 <= (day - s).days < days else []
    if kind == "once":
        return times if day.isoformat() == (rule.get("date") or "")[:10] else []
    if kind == "mealOffset":
        return []
    return times


def meal_slots(plan, day):
    """餐前/餐后：按当天第一条饮食记录推算（文档的“相对一餐的偏移”）"""
    rule = rule_of(plan)
    if rule.get("kind") != "mealOffset":
        return []
    offset = int(rule.get("offset", 30))
    with connect() as conn:
        row = conn.execute(
            "SELECT occurred_at FROM records WHERE user_id=? AND type='diet' AND deleted=0"
            " AND superseded_by='' AND occurred_at LIKE ? ORDER BY occurred_at LIMIT 1",
            (plan["user_id"], day.isoformat() + "%")).fetchone()
    if not row:
        return plan_times(plan) if offset <= 0 else []
    base = datetime.strptime(row["occurred_at"][:16], "%Y-%m-%d %H:%M")
    return [(base + timedelta(minutes=offset)).strftime("%H:%M")]


# ================================================================ 实例物化
def occ_id(plan_id, slot_local):
    """实例身份 = 计划 + 本地墙钟（不是 UTC 时刻）。

    这样换时区时同一条提醒还是同一行（只重算 due_at），不会凭空多出一条。
    """
    ns = uuid.UUID("0a2f7d59-5c3e-4f0a-9a6e-3d1c8b2e4f61")
    return str(uuid.uuid5(ns, "%s|%s" % (plan_id, slot_local)))


def ensure_occurrences(user_id, day_from, day_to, conn=None):
    """把 [day_from, day_to] 的实例落表；幂等由 UNIQUE(plan_id, due_at) 保证。"""
    own = conn is None
    conn = conn or connect()
    created = 0
    try:
        plans = conn.execute("SELECT * FROM plans WHERE user_id=? AND active=1", (user_id,)).fetchall()
        d = day_from
        while d <= day_to:
            for raw in plans:
                plan = dict(raw)
                plan_created = (plan["created_at"] or "")[:10]
                if plan_created and d.isoformat() < plan_created:
                    continue
                for hhmm in slots_on(plan, d) + meal_slots(plan, d):
                    hh, mm = [int(x) for x in hhmm.split(":")]
                    slot_local = "%s %02d:%02d" % (d.isoformat(), hh, mm)
                    local_due = datetime(d.year, d.month, d.day, hh, mm, tzinfo=tzinfo())
                    due_utc = iso(local_due)
                    oid = occ_id(plan["id"], slot_local)
                    cur = conn.execute(
                        "INSERT OR IGNORE INTO occurrences (id,user_id,plan_id,slot_local,due_at,"
                        "title_snap,dose_snap,kind_snap,state,created_at,updated_at)"
                        " VALUES (?,?,?,?,?,?,?,?, 'pending', ?, ?)",
                        (oid, user_id, plan["id"], slot_local, due_utc,
                         plan["title"], plan["dose"], plan["kind"], iso(utc_now()), iso(utc_now())))
                    created += cur.rowcount
                    if cur.rowcount == 0:
                        # 已存在：时区/规则改了（比如 DST）就重算到期时刻，身份不变
                        conn.execute(
                            "UPDATE occurrences SET due_at=? WHERE plan_id=? AND slot_local=?"
                            " AND due_at<>? AND state='pending'",
                            (due_utc, plan["id"], slot_local, due_utc))
            d += timedelta(days=1)
    finally:
        if own:
            conn.commit()   # 自开连接必须显式提交，否则 close() 会回滚
            conn.close()
    return created


class DiskFull(RuntimeError):
    """磁盘剩余空间低于水位时抛出，接口层转 507。"""


def ensure_disk():
    try:
        free_mb = shutil.disk_usage(os.path.dirname(DB_PATH) or ".").free / (1024 * 1024)
    except OSError:
        return
    if free_mb < CONFIG["disk_min_mb"]:
        raise DiskFull("磁盘剩余 %.0f MB，低于水位 %d MB，已停止写入" % (free_mb, CONFIG["disk_min_mb"]))


_pair_hits = {}


def pair_rate_limited(ip):
    """每地址每分钟最多 CONFIG["pair_per_min"] 次配对尝试。"""
    now = time.time()
    with _lock:
        hits = [t for t in _pair_hits.get(ip, []) if now - t < 60]
        if len(hits) >= CONFIG["pair_per_min"]:
            _pair_hits[ip] = hits
            return True
        hits.append(now)
        _pair_hits[ip] = hits
        return False


def occ_row(conn, oid):
    row = conn.execute("SELECT * FROM occurrences WHERE id=?", (oid,)).fetchone()
    return dict(row) if row else None


# ================================================================ 唯一状态入口
def transition(oid, action, actor="", source="app", client_ts="", payload=None, conn=None):
    """唯一允许改 occurrences.state 的函数（文档 4.2.5）。"""
    own = conn is None
    conn = conn or connect()
    try:
        ensure_disk()
        with _lock:
            occ = occ_row(conn, oid)
            if not occ:
                raise LookupError("实例不存在")
            # 契约 409：已经是终态、又提交相反结论
            if occ["state"] == "confirmed" and action in ("missed", "snoozed"):
                raise ChildProcessError("该实例已确认，不能再记为 %s" % action)
            now = utc_now()
            payload = payload or {}
            event_id = (payload.get("event_id") if isinstance(payload, dict) else "") or str(
                uuid.uuid5(uuid.UUID("7c1e5b93-2f47-4d18-8a63-59f0c2b7e14d"),
                           "%s|%s|%s" % (oid, action, client_ts or iso(now))))

            # 先算迁移结果再写事件：payload 里要带上迁移前后状态（文档 4.2.5「单查询可解释」）
            prev_state = occ["state"]
            state, level = prev_state, occ["level"]
            snooze_count = occ["snooze_count"]
            notified_at, confirmed_at, missed_at = occ["notified_at"], occ["confirmed_at"], occ["missed_at"]
            reason = action

            if action == "confirmed":
                state, confirmed_at = "confirmed", iso(now)
            elif action == "missed":
                state, missed_at, level = "missed", iso(now), 3
            elif action == "snoozed":
                if snooze_count >= CONFIG["snooze_max"]:
                    state, missed_at, level = "missed", iso(now), 3
                    reason = "snooze_limit"
                else:
                    snooze_count += 1
                    state = "snoozed"
            elif action == "notified":
                state = "notified"
                notified_at = notified_at or iso(now)
                level = max(level, 1)
            elif action == "escalated":
                state, level = "escalated", max(level, 2)
            elif action in ("reopen", "undo"):
                # 第 5 步：只允许撤销「刚刚」的确认，过窗口就是 409
                last = conn.execute(
                    "SELECT at_utc FROM events WHERE occurrence_id=? AND action='confirmed'"
                    " ORDER BY id DESC LIMIT 1", (oid,)).fetchone()
                if not last:
                    raise ValueError("这条没有可撤销的确认")
                if minutes_since(last["at_utc"], now) * 60 > CONFIG["undo_seconds"]:
                    raise TimeoutError("撤销窗口已过（%d 秒）" % CONFIG["undo_seconds"])
                state, level = "pending", 0
                confirmed_at = ""

            merge = dict(payload)
            merge.update({"client_ts": client_ts, "prev_state": prev_state, "new_state": state,
                          "level": level, "reason": reason})

            cur = conn.execute(
                "INSERT OR IGNORE INTO events (event_id,occurrence_id,user_id,action,actor,source,"
                "payload,at_utc,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (event_id, oid, occ["user_id"], action, actor or "", source,
                 json.dumps(merge, ensure_ascii=False), iso(now), iso(now)))
            if cur.rowcount == 0:
                return {"event": {"event_id": event_id, "occurrence_id": oid, "action": action,
                                  "actor": actor or "", "source": source, "at": iso(now),
                                  "duplicate": True},
                        "event_id": event_id, "duplicate": True, "state": prev_state,
                        "snooze_count": occ["snooze_count"]}

            conn.execute(
                "UPDATE occurrences SET state=?,level=?,snooze_count=?,notified_at=?,confirmed_at=?,"
                "missed_at=?,updated_at=? WHERE id=?",
                (state, level, snooze_count, notified_at, confirmed_at, missed_at, iso(now), oid))

            publish("home/reminder/%s/state" % occ["user_id"],
                    {"occurrence": oid, "plan_id": occ["plan_id"], "due_at": occ["due_at"],
                     "action": action, "state": state, "actor": actor, "event_id": event_id}, conn)

            if action == "confirmed":
                _ack_open_alarms(conn, oid)
            if state in ("missed", "escalated"):
                row = conn.execute("SELECT title FROM plans WHERE id=?", (occ["plan_id"],)).fetchone()
                title = row["title"] if row else occ["plan_id"]
                msg = ("未确认：" if state == "missed" else "仍未确认，已升级：") + \
                      "%s %s" % (title, local_str(occ["due_at"], "%H:%M"))
                _alarm_once(conn, occ["user_id"], "missed" if state == "missed" else "escalated",
                            level, oid, msg)

            result = {"event": {"event_id": event_id, "occurrence_id": oid, "action": action,
                                 "actor": actor or "", "source": source, "at": iso(now),
                                 "prev_state": prev_state, "new_state": state, "level": level},
                      "event_id": event_id, "duplicate": False, "state": state,
                      "level": level, "snooze_count": snooze_count}
        if own:
            conn.commit()          # 自己开的连接必须显式提交，否则 close() 会回滚
        return result
    except Exception:
        if own:
            conn.rollback()
        raise
    finally:
        if own:
            conn.close()


def _alarm_once(conn, user_id, kind, level, oid, message):
    if oid:
        dup = conn.execute("SELECT 1 FROM alarms WHERE occurrence=? AND kind=? AND level=? LIMIT 1",
                           (oid, kind, level)).fetchone()
        if dup:
            return None
    aid = "a-" + uuid.uuid4().hex[:12]
    conn.execute("INSERT INTO alarms (id,user_id,kind,level,occurrence,message,created_at)"
                 " VALUES (?,?,?,?,?,?,?)",
                 (aid, user_id, kind, level, oid, message, iso(utc_now())))
    publish("home/alarm/%s" % user_id,
            {"id": aid, "kind": kind, "level": level, "occurrence": oid, "message": message}, conn)
    try:
        notify(kind, message, {"user_id": user_id, "alarm": aid, "level": level})
    except Exception:
        pass
    return aid


def _ack_open_alarms(conn, oid):
    conn.execute("UPDATE alarms SET acked_at=? WHERE occurrence=? AND acked_at=''",
                 (iso(utc_now()), oid))


def publish(topic, payload, conn=None):
    """所有对外事件的唯一出口：本地写 outbox，云模式换成 MQTT/Webhook 即可。"""
    own = conn is None
    conn = conn or connect()
    try:
        conn.execute("INSERT INTO outbox (topic,payload,created_at) VALUES (?,?,?)",
                     (topic, json.dumps(payload, ensure_ascii=False), iso(utc_now())))
        if own:
            conn.commit()
    finally:
        if own:
            conn.close()


def sos(user_id, actor, note="", device=""):
    """第 6 步：老人长按呼救 → level 3 告警 + 推给家属/社区（走同一个 outbox）。"""
    msg = "呼救：%s" % (note or "老人按下了呼救键")
    if device:
        msg += "（设备 %s）" % device
    with connect() as conn:
        aid = _alarm_once(conn, user_id, "sos", 3, "", msg)
        family = [r["family_id"] for r in conn.execute(
            "SELECT family_id FROM links WHERE elder_id=? ORDER BY created_at", (user_id,)).fetchall()]
        if aid is None:
            row = conn.execute("SELECT id FROM alarms WHERE user_id=? AND kind='sos'"
                               " ORDER BY created_at DESC LIMIT 1", (user_id,)).fetchone()
            aid = row["id"] if row else ""
    return {"id": aid, "kind": "sos", "level": 3, "notified": family,
            "at": iso(utc_now()), "message": msg}


def ingest_presence(user_id, present=True, source="sensor"):
    """第 8 步接口层：屋里有没有人。presence 事件会自动压制「没动静」告警。"""
    with connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO events (event_id,occurrence_id,user_id,action,actor,source,"
            "payload,at_utc,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            ("presence:%s:%s" % (user_id, iso(utc_now())), "", user_id, "presence", source, "sensor",
             json.dumps({"present": bool(present)}, ensure_ascii=False), iso(utc_now()), iso(utc_now())))
    publish("home/sensor/presence", {"user_id": user_id, "present": bool(present), "source": source})
    return {"user_id": user_id, "present": bool(present), "source": source, "at": iso(utc_now())}


def inactivity_check(now=None):
    """第 6 步：太久没动静也报警（多久算久可配）。"""
    now = now or utc_now()
    hours = CONFIG["inactivity_hours"]
    if hours <= 0:
        return 0
    fired = 0
    with connect() as conn:
        elders = [r["id"] for r in conn.execute("SELECT id FROM users WHERE role='elder'").fetchall()]
        for uid in elders:
            last_ev = conn.execute("SELECT at_utc FROM events WHERE user_id=? ORDER BY id DESC LIMIT 1",
                                   (uid,)).fetchone()
            last_rec = conn.execute("SELECT created_at FROM records WHERE user_id=?"
                                   " ORDER BY created_at DESC LIMIT 1", (uid,)).fetchone()
            stamps = [r[0] for r in (last_ev, last_rec) if r and r[0]]
            last = max(stamps) if stamps else None
            if last is None:
                continue
            if minutes_since(last, now) < hours * 60:
                continue
            dup = conn.execute("SELECT 1 FROM alarms WHERE user_id=? AND kind='inactivity'"
                               " AND created_at>=? LIMIT 1",
                               (uid, iso(now - timedelta(hours=hours)))).fetchone()
            if dup:
                continue
            _alarm_once(conn, uid, "inactivity", 2, "",
                        "已经 %.1f 小时没有确认或记录，请确认老人情况" % (minutes_since(last, now) / 60))
            fired += 1
    return fired


def notify(kind, message, meta=None):
    """第 6 步：告警发出去。配了 CAREMATE_WEBHOOK_URL 就真发一次 HTTP POST（短信网关/钉钉/自建都行）。"""
    url = CONFIG["webhook_url"]
    if not url:
        return {"sent": False, "reason": "未配置 CAREMATE_WEBHOOK_URL（演示可指向任意收件端点）"}
    body = json.dumps({"kind": kind, "message": message, **(meta or {})}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return {"sent": True, "status": resp.status, "url": url}
    except Exception as exc:  # noqa: BLE001
        return {"sent": False, "reason": str(exc), "url": url}


def raise_alarm(user_id, kind, level, occurrence, message):
    with connect() as conn:
        return _alarm_once(conn, user_id, kind, level, occurrence, message)


# ================================================================ 调度器（文档 4.2.3）
def scheduler_tick(now=None):
    now = now or utc_now()
    stats = {"scanned": 0, "notified": 0, "escalated": 0, "missed": 0}
    with connect() as conn:
        users = [r["id"] for r in conn.execute("SELECT id FROM users WHERE role='elder'").fetchall()]
        local_today = now.astimezone(tzinfo()).date()
        for uid in users:
            ensure_occurrences(uid, local_today - timedelta(days=1), local_today + timedelta(days=1), conn)
        rows = conn.execute(
            "SELECT * FROM occurrences WHERE state IN ('pending','notified','escalated','snoozed')"
        ).fetchall()
    for row in rows:
        stats["scanned"] += 1
        late = minutes_since(row["due_at"], now)
        if late < 0:
            continue
        if row["state"] == "snoozed":
            if minutes_since(row["updated_at"], now) >= CONFIG["snooze_gap"]:
                transition(row["id"], "notified", actor="scheduler", source="scheduler")
                stats["notified"] += 1
            continue
        # 补齐链条：越过某级时先把 sent 记录补上，保证日志能解释"为什么升级"
        if late >= CONFIG["th2"] and not row["notified_at"]:
            transition(row["id"], "notified", actor="scheduler", source="scheduler")
            stats["notified"] += 1
            row = dict(row)
            row["notified_at"] = iso(now)
        if late >= CONFIG["th3"]:
            transition(row["id"], "missed", actor="scheduler", source="scheduler")
            stats["missed"] += 1
        elif late >= CONFIG["th2"] and row["state"] != "escalated":
            transition(row["id"], "escalated", actor="scheduler", source="scheduler")
            stats["escalated"] += 1
        elif late >= CONFIG["th1"] and row["state"] == "pending":
            transition(row["id"], "notified", actor="scheduler", source="scheduler")
            stats["notified"] += 1
    try:
        stats["inactivity"] = inactivity_check(now)
    except Exception as exc:  # noqa: BLE001
        print("[scheduler] 无动静检查出错：%s" % exc)
    return stats


def scheduler_loop(stop_evt):
    print("[scheduler] 每 %d 秒扫描一次到期实例（阈值 %d/%d/%d 分钟）"
          % (TICK, CONFIG["th1"], CONFIG["th2"], CONFIG["th3"]))
    while not stop_evt.is_set():
        try:
            s = scheduler_tick()
            try:
                with connect() as conn:
                    conn.execute("INSERT OR REPLACE INTO meta (k,v) VALUES ('last_tick', ?)",
                                 (json.dumps({"at": iso(utc_now()), **s}, ensure_ascii=False),))
                    conn.execute("INSERT OR REPLACE INTO meta (k,v) VALUES ('tick_interval', ?)",
                                 (str(TICK),))
            except Exception:
                pass
            if any(s[k] for k in ("notified", "escalated", "missed")):
                print("[scheduler] 扫描 %d 条 → 通知 %d / 升级 %d / 未确认 %d"
                      % (s["scanned"], s["notified"], s["escalated"], s["missed"]))
        except Exception as exc:  # noqa: BLE001
            print("[scheduler] 出错：%s" % exc)
        stop_evt.wait(TICK)


# ================================================================ 查询
def occ_view(row, conn=None):
    row = dict(row) if not isinstance(row, dict) else row
    plan = None
    if conn is not None and not row.get("title_snap"):
        p = conn.execute("SELECT title,kind,dose,note FROM plans WHERE id=?", (row["plan_id"],)).fetchone()
        plan = dict(p) if p else None
    due_local = local_dt(row["due_at"])
    return {
        "id": row["id"], "occurrence": row["id"], "plan_id": row["plan_id"],
        "title": row.get("title_snap") or (plan or {}).get("title", row["plan_id"]),
        "kind": row.get("kind_snap") or (plan or {}).get("kind", ""),
        "dose": row.get("dose_snap") or (plan or {}).get("dose", ""),
        "slot_local": row.get("slot_local") or local_str(row["due_at"]),
        "due_at_utc": row["due_at"],
        "due_at_local": local_str(row["due_at"]),
        "slot": local_str(row["due_at"]),          # 兼容旧前端
        "time_local": due_local.strftime("%H:%M") if due_local else "",
        "date_local": due_local.strftime("%Y-%m-%d") if due_local else "",
        "state": row["state"], "level": row["level"],
        "snooze_count": row["snooze_count"],
        "snoozes": row["snooze_count"],            # 兼容旧前端
        "snooze_left": max(0, CONFIG["snooze_max"] - row["snooze_count"]),
        "late_min": int(max(0, minutes_since(row["due_at"]))),
        "notified_at": row["notified_at"],
        "notified_local": local_str(row["notified_at"], "%H:%M"),
        "confirmed_at": row["confirmed_at"],
        "missed_at": row["missed_at"],
    }


def occurrences(user_id, day=None, horizon=1, conn=None):
    own = conn is None
    conn = conn or connect()
    try:
        day = day or utc_now().astimezone(tzinfo()).date()
        ensure_occurrences(user_id, day - timedelta(days=1), day + timedelta(days=horizon), conn)
        start = datetime(day.year, day.month, day.day, tzinfo=tzinfo())
        end = start + timedelta(days=horizon)
        rows = conn.execute(
            "SELECT * FROM occurrences WHERE user_id=? AND due_at>=? AND due_at<? ORDER BY due_at",
            (user_id, iso(start), iso(end))).fetchall()
        return [occ_view(r, conn) for r in rows]
    finally:
        if own:
            conn.commit()   # 读之前顺带物化了实例，同样要提交
            conn.close()


def today_occurrences(user_id):
    return occurrences(user_id, utc_now().astimezone(tzinfo()).date(), 1)


# ================================================================ 记录（追加式更正）
RECORD_TYPES = ("sleep_start", "sleep_end", "water", "activity", "diet", "mood")
RECORD_UNITS = {"water": "ml", "activity": "min", "diet": "kcal"}


def add_record(user_id, body, creator):
    rtype = body.get("type")
    if rtype not in RECORD_TYPES:
        raise ValueError("type 必须是 %s" % "、".join(RECORD_TYPES))
    occurred = body.get("occurred_at") or body.get("at") or utc_now().astimezone(tzinfo()).strftime("%Y-%m-%d %H:%M")
    if "T" in str(occurred):              # 契约：ISO 8601 带时区
        dt = parse_iso(str(occurred))
        if dt:
            occurred = dt.astimezone(tzinfo()).strftime("%Y-%m-%d %H:%M")
    try:
        datetime.strptime(occurred, "%Y-%m-%d %H:%M")
    except ValueError:
        raise ValueError("occurred_at 格式应为 YYYY-MM-DD HH:MM")
    ensure_disk()
    rid = "r-" + uuid.uuid4().hex[:12]
    with _lock, connect() as conn:
        conn.execute(
            "INSERT INTO records (id,user_id,type,value,unit,occurred_at,note,created_by,created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (rid, user_id, rtype, body.get("value"), body.get("unit") or RECORD_UNITS.get(rtype, ""),
             occurred, body.get("note", ""), creator, iso(utc_now())))
    publish("home/record/%s" % user_id, {"id": rid, "type": rtype, "occurred_at": occurred})
    return {"id": rid, "revision": 1}


def correct_record(rid, body, actor):
    """更正 = 新写一条 revision+1 的记录；旧记录 superseded_by 指向新记录（append-only，永不覆盖）"""
    with _lock, connect() as conn:
        row = conn.execute("SELECT * FROM records WHERE id=?", (rid,)).fetchone()
        if not row:
            raise ValueError("记录不存在")
        if row["superseded_by"]:
            raise ValueError("该记录已被更正过，请在最新版本上修改")
        new_id = "r-" + uuid.uuid4().hex[:12]
        conn.execute(
            "INSERT INTO records (id,user_id,type,value,unit,occurred_at,note,created_by,updated_by,"
            "revision,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (new_id, row["user_id"], row["type"],
             body.get("value", row["value"]), body.get("unit", row["unit"]),
             body.get("occurred_at", row["occurred_at"]), body.get("note", row["note"]),
             row["created_by"], actor, (row["revision"] or 1) + 1, iso(utc_now())))
        conn.execute("UPDATE records SET superseded_by=? WHERE id=?", (new_id, rid))
    publish("home/record/%s" % row["user_id"], {"id": new_id, "supersedes": rid, "by": actor})
    return {"id": new_id, "supersedes": rid, "revision": (row["revision"] or 1) + 1}


def delete_record(rid, actor):
    with _lock, connect() as conn:
        row = conn.execute("SELECT * FROM records WHERE id=?", (rid,)).fetchone()
        if not row:
            raise ValueError("记录不存在")
        if row["deleted"]:
            raise ValueError("这条已经撤销过了")
        # 第 4 步：记完 30 分钟内能撤，超时要家属在更正通道处理
        age_min = minutes_since(row["created_at"])
        if age_min > CONFIG["record_undo_minutes"]:
            raise TimeoutError("超过 %d 分钟，不能再撤销；请用更正" % CONFIG["record_undo_minutes"])
        conn.execute("UPDATE records SET deleted=1,updated_by=?,revision=revision+1 WHERE id=?",
                     (actor, rid))
        # 留痕：谁、什么时候、撤的哪条（写进事件表，跟着导出一起来）
        conn.execute(
            "INSERT OR IGNORE INTO events (event_id,occurrence_id,user_id,action,actor,source,"
            "payload,at_utc,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            ("rec-undo:" + rid + ":" + iso(utc_now()), rid, row["user_id"], "record_deleted",
             actor, "web", json.dumps({"record": rid, "type": row["type"],
                                       "value": row["value"], "aged_minutes": round(age_min, 1)},
                                      ensure_ascii=False), iso(utc_now()), iso(utc_now())))
    publish("home/record/%s" % row["user_id"], {"id": rid, "deleted": True, "by": actor})
    return {"id": rid, "deleted": True}


def list_records(user_id, days=7, include_history=False):
    start = (utc_now().astimezone(tzinfo()).date() - timedelta(days=days - 1)).isoformat() + " 00:00"
    sql = "SELECT * FROM records WHERE user_id=? AND occurred_at>=?"
    if not include_history:
        sql += " AND superseded_by='' AND deleted=0"
    sql += " ORDER BY occurred_at DESC"
    with connect() as conn:
        return [dict(r) for r in conn.execute(sql, (user_id, start)).fetchall()]


# ================================================================ 统计
def stats(user_id, days=7):
    today = utc_now().astimezone(tzinfo()).date()
    start = today - timedelta(days=days - 1)
    with connect() as conn:
        ensure_occurrences(user_id, start, today, conn)
        rows = conn.execute(
            "SELECT * FROM occurrences WHERE user_id=? AND due_at>=? AND due_at<? ORDER BY due_at",
            (user_id, iso(datetime(start.year, start.month, start.day, tzinfo=tzinfo())),
             iso(datetime(today.year, today.month, today.day, tzinfo=tzinfo()) + timedelta(days=1))),
        ).fetchall()
        recs = conn.execute(
            "SELECT type,COUNT(*) c,COALESCE(SUM(value),0) v FROM records"
            " WHERE user_id=? AND deleted=0 AND superseded_by='' AND occurred_at>=?"
            " GROUP BY type", (user_id, start.isoformat() + " 00:00")).fetchall()
        alarm_count = conn.execute(
            "SELECT COUNT(*) c FROM alarms WHERE user_id=? AND created_at>=?",
            (user_id, iso(datetime(start.year, start.month, start.day, tzinfo=tzinfo())))).fetchone()

    now = utc_now()
    due = [r for r in rows if minutes_since(r["due_at"], now) >= 0]
    confirmed = sum(1 for r in due if r["state"] == "confirmed")
    missed = sum(1 for r in due if r["state"] == "missed")
    pending = sum(1 for r in due if r["state"] in ("pending", "notified", "escalated", "snoozed"))

    per_day = {}
    for r in rows:
        key = local_str(r["due_at"], "%Y-%m-%d")
        b = per_day.setdefault(key, {"date": key, "confirmed": 0, "missed": 0, "other": 0})
        if r["state"] == "confirmed":
            b["confirmed"] += 1
        elif r["state"] == "missed":
            b["missed"] += 1
        else:
            b["other"] += 1

    streak = 0
    for i in range(days):
        key = (today - timedelta(days=i)).isoformat()
        b = per_day.get(key)
        if not b or b["missed"]:
            break
        streak += 1

    return {
        "days": days, "total": len(due), "planned": len(rows),
        "confirmed": confirmed, "missed": missed, "pending": pending,
        "completion": round(confirmed / len(due), 3) if due else None,
        "streak_days": streak,
        "alarms": alarm_count["c"] if alarm_count else 0,
        "by_day": [per_day[k] for k in sorted(per_day)],
        "records": {r["type"]: {"count": r["c"], "sum": r["v"]} for r in recs},
        "caliber": {
            "period": "自然日 00:00–23:59（%s，库内按 UTC 存）" % CONFIG["tz"],
            "completion": "confirmed ÷ 已到期实例（未到点不计入分母）",
            "missing": "漏记按“缺失”处理，不当成 0",
            "expired": "超过 %d 分钟未确认记为 missed" % CONFIG["th3"],
        },
    }


# ================================================================ 指标
def dispatch_stats(days=7):
    """派发延迟 = notified_at - due_at，文档 4.2.6 的「≤30 s @ P95」。"""
    since = iso(utc_now() - timedelta(days=days))
    with connect() as conn:
        rows = conn.execute(
            "SELECT due_at, notified_at FROM occurrences"
            " WHERE notified_at<>'' AND due_at>=? AND created_at<>'' AND created_at<=due_at",
            (since,)).fetchall()
        backfill = conn.execute(
            "SELECT COUNT(*) c FROM occurrences WHERE notified_at<>'' AND created_at>due_at"
        ).fetchone()["c"]
        last = conn.execute("SELECT v FROM meta WHERE k='last_tick'").fetchone()
        interval = conn.execute("SELECT v FROM meta WHERE k='tick_interval'").fetchone()
        counts = {r["state"]: r["c"] for r in conn.execute(
            "SELECT state, COUNT(*) c FROM occurrences GROUP BY state").fetchall()}
    delays = []
    for r in rows:
        d0, d1 = parse_iso(r["due_at"]), parse_iso(r["notified_at"])
        if d0 and d1:
            delays.append(max(0.0, (d1 - d0).total_seconds()))
    delays.sort()

    def pct(p):
        return round(delays[min(len(delays) - 1, int(len(delays) * p))], 2) if delays else None

    return {"samples": len(delays), "backfill_excluded": backfill, "p50": pct(0.50), "p95": pct(0.95),
            "max": round(delays[-1], 2) if delays else None,
            "tick_seconds": int(interval["v"]) if interval else TICK,
            "threshold_seconds": TICK,
            "states": counts,
            "last_tick": json.loads(last["v"]) if last else None}


def do_backup(dest_dir=None):
    """SQLite 在线备份，可直接放进 cron / 计划任务。"""
    dest_dir = dest_dir or os.environ.get("CAREMATE_BACKUP_DIR", os.path.join(BASE, "backups"))
    os.makedirs(dest_dir, exist_ok=True)
    name = "caremate-%s.db" % utc_now().astimezone(tzinfo()).strftime("%Y%m%d-%H%M%S")
    path = os.path.join(dest_dir, name)
    with connect() as src, sqlite3.connect(path) as dst:
        src.backup(dst)
    size = os.path.getsize(path) / 1024
    print("备份完成：%s（%.0f KB）" % (path, size))
    return path


# ================================================================ 排程预览（第 1 步验收用）
def plan_preview(user_id, days=7, day=None):
    """不等待真实时间，直接把未来 N 天的实例算出来——文档要的「拿纸对一遍」。"""
    start = day or utc_now().astimezone(tzinfo()).date()
    out = []
    with connect() as conn:
        plans = conn.execute("SELECT * FROM plans WHERE user_id=? AND active=1", (user_id,)).fetchall()
        d = start
        for _ in range(days):
            for raw in plans:
                plan = dict(raw)
                created = (plan["created_at"] or "")[:10]
                if created and d.isoformat() < created:
                    continue
                for hhmm in sorted(set(slots_on(plan, d) + meal_slots(plan, d))):
                    hh, mm = [int(x) for x in hhmm.split(":")]
                    local_due = datetime(d.year, d.month, d.day, hh, mm, tzinfo=tzinfo())
                    out.append({"date": d.isoformat(), "time": hhmm,
                                "due_at_utc": iso(local_due), "plan_id": plan["id"],
                                "title": plan["title"], "dose": plan["dose"],
                                "rule": rule_of(plan).get("kind", "daily")})
            d += timedelta(days=1)
    out.sort(key=lambda x: (x["date"], x["time"]))
    return out


# ================================================================ 计划写入
def save_plan(user_id, body, plan_id=None):
    if plan_id and set(body.keys()) <= {"active", "user_id", "paused_until"}:
        with _lock, connect() as conn:
            if "paused_until" in body:
                conn.execute("UPDATE plans SET paused_until=?,updated_at=? WHERE id=? AND user_id=?",
                             (body.get("paused_until") or "", iso(utc_now()), plan_id, user_id))
            conn.execute("UPDATE plans SET active=?,updated_at=? WHERE id=? AND user_id=?",
                         (1 if body.get("active", 1) else 0, iso(utc_now()), plan_id, user_id))
        return {"id": plan_id}

    times = normalize_times(body.get("times") or [])
    rule = body.get("rule") or {}
    if isinstance(rule, str):
        try:
            rule = json.loads(rule)
        except ValueError:
            rule = {}
    kind = (rule.get("kind") or "daily").strip()
    if kind == "meal_offset":             # 契约写法
        kind = "mealOffset"
        rule["kind"] = kind
    if kind == "once" and not rule.get("date"):
        # 契约：once 用 at（ISO 时间或日期）
        at = str(rule.get("at") or rule.get("time") or "")
        if at:
            rule["date"] = at.split("T")[0]
            if "T" in at:
                rule["times"] = [at.split("T")[1][:5]]
    if kind not in ("daily", "weekly", "interval", "monthly", "course", "once", "mealOffset"):
        raise ValueError("重复规则只能是 daily/interval/weekly/monthly/course/meal_offset/once")
    if not times and kind != "mealOffset":
        raise ValueError("时刻格式不对，请写成 08:00（多条用逗号分隔）")
    if kind == "once" and not rule.get("date"):
        raise ValueError("一次性提醒需要 date（YYYY-MM-DD）")
    weekdays = normalize_weekdays(body.get("weekdays") or rule.get("weekdays") or [])

    with _lock, connect() as conn:
        if plan_id:
            conn.execute(
                "UPDATE plans SET title=?,kind=?,times=?,weekdays=?,rule=?,dose=?,note=?,active=?,updated_at=?"
                " WHERE id=? AND user_id=?",
                (body.get("title", ""), body.get("kind", "medication"), ",".join(times),
                 ",".join(str(x) for x in weekdays), json.dumps(rule, ensure_ascii=False),
                 body.get("dose", ""), body.get("note", ""), 1 if body.get("active", 1) else 0,
                 iso(utc_now()), plan_id, user_id))
            return {"id": plan_id}
        # 加随机后缀：连建多条计划时 Windows 时钟只有毫秒精度，纯时间戳会撞主键
        pid = "p-" + datetime.now().strftime("%Y%m%d%H%M%S") + uuid.uuid4().hex[:6]
        conn.execute(
            "INSERT INTO plans (id,user_id,title,kind,times,weekdays,rule,dose,note,active,created_at,updated_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (pid, user_id, body.get("title", ""), body.get("kind", "medication"), ",".join(times),
             ",".join(str(x) for x in weekdays), json.dumps(rule, ensure_ascii=False),
             body.get("dose", ""), body.get("note", ""), 1 if body.get("active", 1) else 0,
             iso(utc_now()), iso(utc_now())))
    return {"id": pid}


# ================================================================ HTTP
class Handler(BaseHTTPRequestHandler):
    server_version = "CareMateCloud/" + VERSION
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        if os.environ.get("CAREMATE_QUIET"):
            return
        print("[%s] %s" % (time.strftime("%H:%M:%S"), fmt % args))

    def send_body(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "X-Token, Content-Type, Idempotency-Key")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
        self.send_header("X-Api-Version", "v1")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def json(self, code, obj):
        self.send_body(code, obj)

    def me(self):
        """契约：Authorization: Bearer <token>；兼容 X-Token 与 ?token=。"""
        auth = self.headers.get("Authorization") or ""
        token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
        if not token:
            token = self.headers.get("X-Token") or ""
        if not token:
            token = (parse_qs(urlparse(self.path).query).get("token") or [""])[0]
        return user_by_token(token)

    def _plan_view(self, user_id, plan_id):
        with connect() as conn:
            row = conn.execute("SELECT * FROM plans WHERE id=? AND user_id=?",
                               (plan_id, user_id)).fetchone()
        if not row:
            return {"error": "计划不存在", "id": plan_id}
        d = dict(row)
        d["rule"] = rule_of(d)
        d["times"] = plan_times(d)
        d["weekdays"] = normalize_weekdays(d["weekdays"])
        d["elder_id"] = d["user_id"]
        return d

    def _record_view(self, rid):
        with connect() as conn:
            row = conn.execute("SELECT * FROM records WHERE id=?", (rid,)).fetchone()
        if not row:
            return {"error": "记录不存在", "id": rid}
        d = dict(row)
        d["at"] = d["occurred_at"]
        d["elder_id"] = d["user_id"]
        return d

    def _fail(self, exc, code_map):
        for kind, code in code_map:
            if isinstance(exc, kind):
                return self.json(code, {"error": str(exc)})
        return self.json(500, {"error": str(exc)})

    def body_json(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n).decode("utf-8") or "{}") if n else {}

    def static(self, rel):
        path = os.path.normpath(os.path.join(WEB, rel))
        if not path.startswith(WEB) or not os.path.isfile(path):
            hint = ("<h3>页面文件没找到</h3><p>请求：<code>%s</code><br>应在：<code>%s</code></p>"
                    "<p>请从项目目录启动：<code>cd /d F:\\ppt\\caremate-cloud</code> 再 "
                    "<code>python server.py</code>，或双击 <b>start.bat</b>。</p>" % (rel, path))
            if self.path in ("/", "/index.html"):
                return self.send_body(500, hint, "text/html; charset=utf-8")
            return self.json(404, {"error": "not found", "expected": path})
        ctype = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
                 ".js": "application/javascript; charset=utf-8", ".png": "image/png",
                 ".webmanifest": "application/manifest+json; charset=utf-8",
                 ".json": "application/json; charset=utf-8",
                 ".svg": "image/svg+xml"}.get(os.path.splitext(path)[1].lower(), "application/octet-stream")
        with open(path, "rb") as fh:
            self.send_body(200, fh.read(), ctype)

    def _dispatch(self, impl):
        try:
            impl()
        except DiskFull as exc:
            try:
                self.json(507, {"error": str(exc)})
            except Exception:
                pass
        except Exception as exc:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            try:
                self.json(500, {"error": "服务器内部错误：%s" % exc})
            except Exception:
                pass

    def do_GET(self):
        self._dispatch(self._get)

    def do_POST(self):
        self._dispatch(self._post)

    def do_PUT(self):
        self._dispatch(self._put)

    def do_PATCH(self):
        self._dispatch(self._patch)

    def do_DELETE(self):
        self._dispatch(self._delete)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "X-Token, Content-Type, Idempotency-Key")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
        self.send_header("Content-Length", "0")
        self.end_headers()

    # ---------------- GET
    def _get(self):
        u = urlparse(self.path)
        p, q = u.path, {k: v[0] for k, v in parse_qs(u.query).items()}

        if p in ("/", "/index.html"):
            return self.static("index.html")
        if p in ("/app", "/app/"):
            return self.static("app.html")
        if p in ("/kiosk", "/kiosk/"):
            return self.static("kiosk.html")
        if p in ("/dashboard", "/dashboard/"):
            return self.static("dashboard.html")
        if p.startswith("/static/"):
            return self.static(p[len("/static/"):])
        if p in ("/manifest.webmanifest", "/sw.js", "/icon-192.png", "/icon-512.png",
                 "/apple-touch-icon.png"):
            return self.static(p.lstrip("/"))
        if p == "/favicon.ico":
            return self.send_body(204, b"")

        if p == "/api/v1/health":
            return self.json(200, {"ok": True, "time": iso(utc_now()), "version": VERSION,
                                    "mode": CONFIG["mode"], "scheduler": CONFIG["scheduler"],
                                    "tz": CONFIG["tz"]})
        if p == "/api/v1/version":
            return self.json(200, {
                "version": VERSION, "api": "v1", "mode": CONFIG["mode"],
                "model": ["plan", "occurrence", "event", "record"],
                "states": list(STATES),
                "thresholds": {"t1": CONFIG["th1"], "t2": CONFIG["th2"], "t3": CONFIG["th3"],
                               "snooze_max": CONFIG["snooze_max"]},
                "cloud": {"mqtt": bool(CONFIG["mqtt_url"]), "jwt": bool(CONFIG["jwt_secret"]),
                          "webhook": CONFIG["webhook_url"] or ""},
            })

        user = self.me()
        if not user:
            return self.json(401, {"error": "令牌无效（请在页面右上角填令牌）"})

        if p == "/api/v1/me":
            return self.json(200, {"id": user["id"], "name": user["name"], "role": user["role"],
                                   "bind_code": user["bind_code"], "tz": user["tz"],
                                   "paired_elder": user.get("paired_elder"),
                                   "session": bool(user.get("session")),
                                   "expires_at": user.get("expires_at")})

        # 默认目标：会话令牌看自己配对的那个老人；家属账号看第一个绑定的老人；否则看自己
        target = q.get("elder_id") or q.get("user_id") or user.get("paired_elder")
        if not target and user["role"] != "elder":
            with connect() as conn:
                row = conn.execute(
                    "SELECT elder_id FROM links WHERE family_id=? ORDER BY created_at LIMIT 1",
                    (user["id"],)).fetchone()
            target = row["elder_id"] if row else None
        target = target or user["id"]
        if not can_view(user, target):
            return self.json(403, {"error": "尚未与该老人账号绑定"})

        if p == "/api/v1/occurrences":
            # 报告写法：/occurrences?from=&to=（含首尾）；兼容 date= 与 horizon=
            if q.get("from") or q.get("to"):
                today = utc_now().astimezone(tzinfo()).date()
                try:
                    d_from = datetime.strptime(q.get("from") or today.isoformat(), "%Y-%m-%d").date()
                    d_to = datetime.strptime(q.get("to") or d_from.isoformat(), "%Y-%m-%d").date()
                except ValueError:
                    return self.json(400, {"error": "from/to 格式应为 YYYY-MM-DD"})
                if d_to < d_from:
                    return self.json(400, {"error": "to 不能早于 from"})
                span = (d_to - d_from).days + 1
                if span > 62:
                    return self.json(400, {"error": "一次最多查 62 天"})
                items = occurrences(target, d_from, span)
                if q.get("envelope") == "1":
                    return self.json(200, {"elder_id": target, "from": d_from.isoformat(),
                                           "to": d_to.isoformat(), "tz": CONFIG["tz"], "items": items})
                return self.json(200, items)
            day = q.get("date") or utc_now().astimezone(tzinfo()).date().isoformat()
            try:
                d = datetime.strptime(day, "%Y-%m-%d").date()
            except ValueError:
                return self.json(400, {"error": "date 格式应为 YYYY-MM-DD"})
            items = occurrences(target, d, int(q.get("horizon", 1)))
            if q.get("envelope") == "1":
                return self.json(200, {"elder_id": target, "date": day, "tz": CONFIG["tz"], "items": items})
            return self.json(200, items)

        if p == "/api/v1/overview":
            day = q.get("date") or utc_now().astimezone(tzinfo()).date().isoformat()
            try:
                d = datetime.strptime(day, "%Y-%m-%d").date()
            except ValueError:
                return self.json(400, {"error": "date 格式应为 YYYY-MM-DD"})
            with connect() as conn:
                alarms = [self._alarm_view(r) for r in conn.execute(
                    "SELECT * FROM alarms WHERE user_id=? ORDER BY created_at DESC LIMIT 20",
                    (target,)).fetchall()]
                plans = [dict(r) for r in conn.execute(
                    "SELECT * FROM plans WHERE user_id=? ORDER BY times", (target,)).fetchall()]
            for pl in plans:
                pl["rule"] = rule_of(pl)
            return self.json(200, {"date": day, "tz": CONFIG["tz"],
                                   "occurrences": occurrences(target, d, int(q.get("horizon", 1))),
                                   "alarms": alarms, "plans": plans,
                                   "stats": stats(target, int(q.get("days", 7))),
                                   "records": list_records(target, int(q.get("days", 7)))})

        if p == "/api/v1/plans":
            with connect() as conn:
                rows = [dict(r) for r in conn.execute(
                    "SELECT * FROM plans WHERE user_id=? ORDER BY times", (target,)).fetchall()]
            for r in rows:
                r["rule"] = rule_of(r)
            return self.json(200, {"items": rows})

        if p == "/api/v1/records":
            return self.json(200, {"items": list_records(target, int(q.get("days", 7)),
                                                         q.get("history") == "1")})

        if p == "/api/v1/stats":
            days = int(q.get("days") or 7)
            rng = (q.get("range") or "").strip()
            if rng.endswith("d") and rng[:-1].isdigit():
                days = int(rng[:-1])
            st = stats(target, days)
            daily = []
            for row in st["by_day"]:
                total = row["confirmed"] + row["missed"] + row["other"]
                daily.append({"date": row["date"], "confirmed": row["confirmed"],
                              "missed": row["missed"], "pending": row["other"], "total": total,
                              "completion": round(row["confirmed"] / total, 3) if total else None})
            weekly = {}
            for row in st["by_day"]:
                try:
                    d = datetime.strptime(row["date"], "%Y-%m-%d").date()
                except ValueError:
                    continue
                monday = (d - timedelta(days=d.weekday())).isoformat()
                w = weekly.setdefault(monday, {"week_start": monday, "confirmed": 0, "missed": 0,
                                               "pending": 0, "total": 0})
                w["confirmed"] += row["confirmed"]
                w["missed"] += row["missed"]
                w["pending"] += row["other"]
                w["total"] += row["confirmed"] + row["missed"] + row["other"]
            for w in weekly.values():
                w["completion"] = round(w["confirmed"] / w["total"], 3) if w["total"] else None
            return self.json(200, {"elder_id": target, "range": "%dd" % days,
                                   "totals": {k: st[k] for k in ("total", "planned", "confirmed",
                                                                 "missed", "pending", "completion",
                                                                 "streak_days", "alarms")},
                                   "daily": daily,
                                   "weekly": [weekly[k] for k in sorted(weekly)],
                                   "caliber": st["caliber"]})

        if p == "/api/v1/alarms/wait":
            # 长轮询：有新的就马上回，没有就挂起，最长 timeout 秒
            try:
                since = int(q.get("since") or 0)
            except ValueError:
                since = 0
            try:
                timeout = float(q.get("timeout") or 20)
            except ValueError:
                timeout = 20.0
            timeout = max(1.0, min(timeout, 25.0))
            deadline = time.time() + timeout
            while True:
                with connect() as conn:
                    rows = conn.execute(
                        "SELECT rowid AS seq, * FROM alarms WHERE user_id=? AND rowid>?"
                        " ORDER BY rowid LIMIT 20", (target, since)).fetchall()
                    top = conn.execute("SELECT COALESCE(MAX(rowid),0) m FROM alarms"
                                       " WHERE user_id=?", (target,)).fetchone()["m"]
                if rows:
                    items = []
                    for r in rows:
                        d = self._alarm_view(r)
                        d["seq"] = r["seq"]
                        items.append(d)
                    return self.json(200, {"seq": items[-1]["seq"], "items": items,
                                           "server_time": iso(utc_now())})
                if time.time() >= deadline:
                    return self.json(200, {"seq": max(since, top), "items": [],
                                           "server_time": iso(utc_now())})
                time.sleep(0.2)

        if p in ("/api/v1/alerts", "/api/v1/alarms"):
            with connect() as conn:
                if p == "/api/v1/alerts":
                    rows = conn.execute(
                        "SELECT * FROM occurrences WHERE user_id=? AND state IN ('escalated','missed')"
                        " AND confirmed_at='' ORDER BY due_at DESC LIMIT 50", (target,)).fetchall()
                    items = []
                    for r in rows:
                        v = occ_view(r, conn)
                        v["elder_id"] = target
                        v["alert_level"] = v["level"]
                        v["thresholds"] = {"t1": CONFIG["th1"], "t2": CONFIG["th2"], "t3": CONFIG["th3"]}
                        items.append(v)
                    if q.get("envelope") == "1":
                        return self.json(200, {"elder_id": target, "items": items,
                                               "thresholds": {"t1": CONFIG["th1"], "t2": CONFIG["th2"],
                                                              "t3": CONFIG["th3"]}})
                    return self.json(200, items)
                rows = conn.execute("SELECT * FROM alarms WHERE user_id=? ORDER BY created_at DESC LIMIT 100",
                                    (target,)).fetchall()
            return self.json(200, {"items": [self._alarm_view(r) for r in rows]})

        if p == "/api/v1/events":
            with connect() as conn:
                rows = [dict(r) for r in conn.execute(
                    "SELECT * FROM events WHERE user_id=? ORDER BY id DESC LIMIT ?",
                    (target, int(q.get("limit", 200)))).fetchall()]
            for r in rows:
                r["at_local"] = local_str(r["created_at"])
            return self.json(200, {"items": rows})

        if p == "/api/v1/outbox":
            with connect() as conn:
                rows = [dict(r) for r in conn.execute(
                    "SELECT * FROM outbox WHERE delivered_at='' ORDER BY id LIMIT 200").fetchall()]
            return self.json(200, {"items": rows, "mqtt": CONFIG["mqtt_url"] or ""})

        if p == "/api/v1/export.csv":
            return self._export(q, target)

        if p == "/api/v1/sensor/presence":
            return self.json(201, ingest_presence(target, True, source=q.get("source", "sensor")))

        if p == "/api/v1/preview":
            days = int(q.get("days") or 7)
            day = None
            if q.get("date"):
                try:
                    day = datetime.strptime(q["date"], "%Y-%m-%d").date()
                except ValueError:
                    return self.json(422, {"error": "date 格式应为 YYYY-MM-DD"})
            items = plan_preview(target, days, day)
            return self.json(200, {"elder_id": target, "days": days, "tz": CONFIG["tz"],
                                   "count": len(items), "items": items})

        if p == "/api/v1/metrics":
            return self.json(200, dispatch_stats(int(q.get("days", 7))))

        parts = p.strip("/").split("/")
        if len(parts) == 5 and parts[:3] == ["api", "v1", "occurrences"] and parts[4] == "events":
            with connect() as conn:
                occ = conn.execute("SELECT * FROM occurrences WHERE id=?", (parts[3],)).fetchone()
                if not occ or not can_view(user, occ["user_id"]):
                    return self.json(404, {"error": "实例不存在"})
                rows = [dict(r) for r in conn.execute(
                    "SELECT * FROM events WHERE occurrence_id=? ORDER BY id", (parts[3],)).fetchall()]
            for r in rows:
                r["at_local"] = local_str(r["created_at"])
                try:
                    r["payload"] = json.loads(r["payload"])
                except ValueError:
                    pass
            return self.json(200, {"occurrence": occ_view(dict(occ)), "events": rows,
                                   "explain": "一次查询返回该实例的完整迁移链"})

        # ---- App 兼容
        if p in ("/api/v1/app/bundle", "/api/v1/app/due"):
            occ = occurrences(target, utc_now().astimezone(tzinfo()).date(), 1)
            now = utc_now()
            due = [o for o in occ if o["state"] in ("pending", "notified", "escalated", "snoozed")
                   and minutes_since(o["due_at_utc"], now) >= 0 and o["late_min"] <= 45]
            if p.endswith("/due"):
                return self.json(200, {"now": iso(now), "items": due})
            with connect() as conn:
                plans = [dict(r) for r in conn.execute(
                    "SELECT * FROM plans WHERE user_id=? AND active=1", (target,)).fetchall()]
            for pl in plans:
                pl["rule"] = rule_of(pl)
            return self.json(200, {"now": iso(now), "user_id": target, "plans": plans,
                                   "due": due, "occurrences": occ,
                                   "records": list_records(target, 1)})

        return self.json(404, {"error": "no route", "path": p})

    def _alarm_view(self, r):
        d = dict(r)
        d["created_local"] = local_str(r["created_at"])
        return d

    def _export(self, q, target):
        kind = q.get("type", "records")
        days = int(q.get("days", 7))
        buf = io.StringIO()
        w = csv.writer(buf)
        if kind == "events":
            w.writerow(["实例", "计划", "到期(本地)", "状态", "级别", "通知时间", "确认时间", "未确认时间"])
            for o in occurrences(target, utc_now().astimezone(tzinfo()).date() - timedelta(days=days - 1), days):
                w.writerow([o["id"][:8], o["title"], o["due_at_local"], o["state"], o["level"],
                            local_str(o["notified_at"]), local_str(o["confirmed_at"]),
                            local_str(o["missed_at"])])
        elif kind == "alarms":
            w.writerow(["时间(本地)", "类型", "级别", "说明", "已读"])
            with connect() as conn:
                for r in conn.execute("SELECT * FROM alarms WHERE user_id=? ORDER BY created_at DESC",
                                      (target,)).fetchall():
                    w.writerow([local_str(r["created_at"]), r["kind"], r["level"], r["message"],
                                "是" if r["acked_at"] else "否"])
        else:
            w.writerow(["时间", "类型", "数值", "单位", "备注", "记录人", "版本", "已被更正为", "已删除"])
            for r in list_records(target, days, include_history=True):
                w.writerow([r["occurred_at"], r["type"], r["value"], r["unit"], r["note"],
                            r["created_by"], r["revision"], r["superseded_by"][:8],
                            "是" if r["deleted"] else "否"])
        raw = ("\ufeff" + buf.getvalue()).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", "attachment; filename=caremate-%s.csv" % kind)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _need_edit(self, user, target):
        if user["role"] == "elder" and target == user["id"]:
            return True
        if user["role"] == "community":
            return False
        lnk = can_view(user, target)
        return bool(lnk and lnk.get("can_edit"))

    # ---------------- POST
    def _post(self):
        p = urlparse(self.path).path
        try:
            body = self.body_json()
        except ValueError:
            return self.json(400, {"error": "请求体不是合法 JSON"})

        if p in ("/api/v1/auth/pair", "/api/v1/bind"):
            # 配对码 → 会话令牌（文档 4.2.7：不发账号密码；4 位码靠限速防枚举）
            ip = (self.headers.get("X-Forwarded-For") or self.client_address[0] or "").split(",")[0].strip()
            if pair_rate_limited(ip):
                self.send_header_retry = 60
                return self.json(429, {
                    "error": "配对尝试过于频繁（每分钟最多 %d 次），请 1 分钟后再试"

                             % CONFIG["pair_per_min"],
                    "retry_after": 60})
            code = str(body.get("pairing_code") or body.get("code") or "").strip()
            with connect() as conn:
                elder = conn.execute("SELECT * FROM users WHERE bind_code=? AND role='elder'",
                                     (code,)).fetchone()
            if not elder:
                return self.json(404, {"error": "配对码不存在"})
            token = "ses-" + secrets.token_urlsafe(24)
            expires = iso(utc_now() + timedelta(days=int(body.get("days", 30))))
            label = str(body.get("label", "照护者"))[:40]
            with _lock, connect() as conn:
                conn.execute("INSERT INTO sessions (token,user_id,elder_id,label,created_at,expires_at)"
                             " VALUES (?,?,?,?,?,?)",
                             (token, "u-family", elder["id"], label, iso(utc_now()), expires))
                conn.execute("INSERT OR IGNORE INTO links (family_id,elder_id,can_edit,created_at)"
                             " VALUES (?,?,?,?)", ("u-family", elder["id"], 1, iso(utc_now())))
            return self.json(201, {"token": token, "elder_id": elder["id"], "name": elder["name"],
                                   "expires_at": expires, "role": "family",
                                   "hint": "把 token 填进页面右上角，或直接留在浏览器里"})

        if p == "/api/v1/auth/logout":
            token = self.headers.get("X-Token") or ""
            with _lock, connect() as conn:
                conn.execute("DELETE FROM sessions WHERE token=?", (token,))
            return self.json(200, {"ok": True})

        user = self.me()
        if not user:
            return self.json(401, {"error": "令牌无效"})
        # 契约用 elder_id；缺省时按「配对老人 → 家属绑定的第一个老人 → 自己」解析
        target = body.get("elder_id") or body.get("user_id") or user.get("paired_elder")
        if not target and user["role"] != "elder":
            with connect() as conn:
                row = conn.execute(
                    "SELECT elder_id FROM links WHERE family_id=? ORDER BY created_at LIMIT 1",
                    (user["id"],)).fetchone()
            target = row["elder_id"] if row else None
        target = target or user["id"]

        parts = p.strip("/").split("/")
        if len(parts) == 5 and parts[:3] == ["api", "v1", "occurrences"] and parts[4] == "events":
            if not self._need_edit(user, target):
                return self.json(403, {"error": "没有权限"})
            try:
                payload = dict(body)
                payload.setdefault("note", body.get("note", ""))
                return self.json(201, transition(parts[3], body.get("action", "confirmed"),
                                                 actor=body.get("actor") or user["id"],
                                                 source=body.get("source", "web"),
                                                 client_ts=body.get("client_ts", ""),
                                                 payload=payload))
            except LookupError as e:
                return self.json(404, {"error": str(e)})
            except (ChildProcessError, TimeoutError) as e:
                return self.json(409, {"error": str(e)})
            except ValueError as e:
                return self.json(422, {"error": str(e)})

        if p == "/api/v1/occurrences/action":
            if not self._need_edit(user, target):
                return self.json(403, {"error": "没有权限"})
            try:
                with connect() as conn:
                    if body.get("occurrence"):
                        oid = body["occurrence"]
                    else:
                        today = utc_now().astimezone(tzinfo()).date()
                        ensure_occurrences(target, today - timedelta(days=1), today + timedelta(days=1), conn)
                        row = conn.execute(
                            "SELECT id FROM occurrences WHERE plan_id=? AND due_at LIKE ?",
                            (body["plan_id"], body["slot"][:10] + "T%")).fetchone()
                        if not row:
                            raise ValueError("找不到对应实例，请先刷新")
                        oid = row["id"]
                return self.json(201, transition(oid, body["action"],
                                                 actor=body.get("actor") or user["id"],
                                                 source=body.get("source", "app"),
                                                 client_ts=body.get("client_ts", "")))
            except KeyError as e:
                return self.json(422, {"error": "缺少字段 %s" % e})
            except LookupError as e:
                return self.json(404, {"error": str(e)})
            except ChildProcessError as e:
                return self.json(409, {"error": str(e)})
            except ValueError as e:
                return self.json(422, {"error": str(e)})

        if p == "/api/v1/plans":
            if not self._need_edit(user, target):
                return self.json(403, {"error": "没有编辑权限"})
            try:
                pid = save_plan(target, body)["id"]
                return self.json(201, self._plan_view(target, pid))
            except (KeyError, ValueError) as e:
                return self.json(422, {"error": "参数不合法：%s" % e})

        if p == "/api/v1/records":
            if not self._need_edit(user, target):
                return self.json(403, {"error": "没有编辑权限"})
            try:
                rid = add_record(target, body, user["id"])["id"]
                return self.json(201, self._record_view(rid))
            except (KeyError, ValueError) as e:
                return self.json(422, {"error": str(e)})

        if p == "/api/v1/alarms/ack":
            with _lock, connect() as conn:
                conn.execute("UPDATE alarms SET acked_at=? WHERE id=? AND user_id=?",
                             (iso(utc_now()), body.get("id", ""), target))
            return self.json(200, {"acked": body.get("id")})

        if p == "/api/v1/sensor/presence":
            return self.json(201, ingest_presence(target, bool(body.get("present", True)),
                                                  body.get("source", "sensor")))

        if p == "/api/v1/notify/test":
            r = notify("test", body.get("message", "这是一条测试通知"),
                       {"user_id": target, "by": user["id"]})
            return self.json(200 if r.get("sent") else 409, r)

        if p in ("/api/v1/sos", "/api/v1/alerts/sos"):
            if not (user["id"] == target or self._need_edit(user, target)):
                return self.json(403, {"error": "没有权限"})
            return self.json(201, sos(target, user["id"], body.get("note", ""),
                                      body.get("device", "")))

        if p == "/api/v1/community/webhook":
            if user["role"] != "community":
                return self.json(403, {"error": "需要社区角色（comm-demo-2026）"})
            aid = raise_alarm(target, body.get("kind", "community"), int(body.get("level", 2)), "",
                              body.get("message", "社区上报"))
            return self.json(201, {"id": aid,
                                   "webhook": CONFIG["webhook_url"] or "(未配置，已落本地告警)"})

        if p == "/api/v1/outbox/drain":
            with _lock, connect() as conn:
                rows = conn.execute("SELECT * FROM outbox WHERE delivered_at='' LIMIT 200").fetchall()
                conn.executemany("UPDATE outbox SET delivered_at=? WHERE id=?",
                                 [(iso(utc_now()), r["id"]) for r in rows])
            return self.json(200, {"delivered": len(rows)})

        if p == "/api/v1/dev/scheduler/tick":
            return self.json(200, scheduler_tick())

        return self.json(404, {"error": "no route", "path": p})

    def _put(self):
        parts = urlparse(self.path).path.strip("/").split("/")
        user = self.me()
        if not user:
            return self.json(401, {"error": "令牌无效"})
        if len(parts) == 4 and parts[:3] == ["api", "v1", "plans"]:
            try:
                body = self.body_json()
            except ValueError:
                return self.json(400, {"error": "请求体不是合法 JSON"})
            target = body.get("elder_id") or body.get("user_id") or user.get("paired_elder") or user["id"]
            if not self._need_edit(user, target):
                return self.json(403, {"error": "没有编辑权限"})
            try:
                save_plan(target, body, plan_id=parts[3])
                return self.json(200, self._plan_view(target, parts[3]))
            except (KeyError, ValueError) as e:
                return self.json(422, {"error": "参数不合法：%s" % e})
        return self.json(404, {"error": "no route"})

    def _patch(self):
        parts = urlparse(self.path).path.strip("/").split("/")
        user = self.me()
        if not user:
            return self.json(401, {"error": "令牌无效"})
        if len(parts) == 4 and parts[:3] == ["api", "v1", "records"]:
            try:
                r = correct_record(parts[3], self.body_json(), user["id"])
                return self.json(200, self._record_view(r["id"]))
            except ValueError as e:
                return self.json(422, {"error": str(e)})
        if len(parts) == 4 and parts[:3] == ["api", "v1", "plans"]:
            try:
                body = self.body_json()
                target = body.get("elder_id") or body.get("user_id") or user.get("paired_elder") or user["id"]
                save_plan(target, body, plan_id=parts[3])
                return self.json(200, self._plan_view(target, parts[3]))
            except (KeyError, ValueError) as e:
                return self.json(422, {"error": "参数不合法：%s" % e})
        return self.json(404, {"error": "no route"})

    def _delete(self):
        parts = urlparse(self.path).path.strip("/").split("/")
        user = self.me()
        if not user:
            return self.json(401, {"error": "令牌无效"})
        if len(parts) == 4 and parts[:3] == ["api", "v1", "records"]:
            try:
                return self.json(200, delete_record(parts[3], user["id"]))
            except TimeoutError as e:
                return self.json(409, {"error": str(e)})
            except ValueError as e:
                return self.json(422, {"error": str(e)})
        if len(parts) == 4 and parts[:3] == ["api", "v1", "plans"]:
            q = parse_qs(urlparse(self.path).query)
            target = (q.get("user_id") or [user["id"]])[0]
            if not self._need_edit(user, target):
                return self.json(403, {"error": "没有编辑权限"})
            with _lock, connect() as conn:
                conn.execute("DELETE FROM plans WHERE id=? AND user_id=?", (parts[3], target))
            return self.json(200, {"deleted": parts[3]})
        return self.json(404, {"error": "no route"})


class Server(ThreadingHTTPServer):
    allow_reuse_address = False
    daemon_threads = True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--backup", action="store_true", help="做一次在线备份后退出（给 cron 用）")
    ap.add_argument("--demo", action="store_true",
                    help="演示预设：升级阈值 1/3/10 分钟、等会儿 5 分钟")
    ap.add_argument("--notify-test", metavar="URL",
                    help="真的往这个地址 POST 一条通知，验证通道（用你自己的 webhook/短信网关）")
    ap.add_argument("--preview", type=int, metavar="DAYS",
                    help="打印未来 N 天的排程表后退出（第 1 步「拿纸对一遍」）")
    args = ap.parse_args()

    init_db()
    if args.backup:
        do_backup()
        return
    if args.notify_test:
        CONFIG["webhook_url"] = args.notify_test
        print("往 %s 发一条测试通知……" % args.notify_test)
        print(notify("test", "CareMate 通知通道自测", {"at": iso(utc_now())}))
        return
    if args.demo:
        CONFIG.update({"th1": 1, "th2": 3, "th3": 10, "snooze_gap": 5})
        print("演示预设：升级 1/3/10 分钟，等会儿 5 分钟")
    if args.preview:
        rows = plan_preview("u-elder", args.preview)
        print("未来 %d 天共 %d 次提醒（时区 %s）" % (args.preview, len(rows), CONFIG["tz"]))
        print("%-12s %-6s %-12s %s" % ("日期", "时刻", "规则", "计划"))
        for r in rows:
            print("%-12s %-6s %-12s %s" % (r["date"], r["time"], r["rule"], r["title"]))
        return
    with connect() as conn:
        today = utc_now().astimezone(tzinfo()).date()
        for r in conn.execute("SELECT id FROM users WHERE role='elder'").fetchall():
            ensure_occurrences(r["id"], today - timedelta(days=1), today + timedelta(days=1), conn)

    try:
        srv = Server((args.host, args.port), Handler)
    except OSError as e:
        print("启动失败：端口 %d 已被占用（%s）" % (args.port, e))
        print("先关掉旧窗口，或换端口： python server.py --port 8001")
        return

    stop_evt = threading.Event()
    if CONFIG["scheduler"]:
        threading.Thread(target=scheduler_loop, args=(stop_evt,), daemon=True).start()

    print("项目目录：", BASE)
    print("数据库  ：", DB_PATH, "| 时区：", CONFIG["tz"], "| 模式：", CONFIG["mode"])
    print("CareMate 云端 v%s 已启动（调度器 %s）：" % (VERSION, "开" if CONFIG["scheduler"] else "关"))
    print("  总入口    http://%s:%d/" % (args.host, args.port))
    print("  App 端    http://%s:%d/app" % (args.host, args.port))
    print("  家属看板  http://%s:%d/dashboard" % (args.host, args.port))
    print("令牌：老人 app-elder-001 / 家属 fam-demo-2026 / 社区 comm-demo-2026")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
    finally:
        stop_evt.set()
        srv.server_close()


if __name__ == "__main__":
    main()
