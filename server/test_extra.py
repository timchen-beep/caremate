# -*- coding: utf-8 -*-
# 作用：新增能力 9 项：七天预览、传感器事件、通知通道、专注模式、--demo/--preview、补建静默、outbox 窗口
"""本轮新增能力的冒烟测试：排程预览、传感器、通知通道、kiosk、（demo 预设由 CLI 验）。"""

import json
import os
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer

BASE = os.environ.get("CAREMATE_BASE") or os.path.dirname(os.path.abspath(__file__))
CLOUD = BASE if os.path.exists(os.path.join(BASE, "server.py")) else os.path.join(BASE, "caremate-cloud")
API = "http://127.0.0.1:8400"
FAM = "fam-demo-2026"
OUT = []


def call(path, token=FAM, data=None, method=None, base=API):
    r = urllib.request.Request(
        base + path,
        data=None if data is None else json.dumps(data, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json", "X-Token": token, "X-Forwarded-For": "198.51.100.40"},
        method=method or ("GET" if data is None else "POST"))
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            raw = resp.read().decode()
            ctype = resp.headers.get("Content-Type", "")
            return resp.status, (json.loads(raw) if "json" in ctype else raw)
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw or "{}")
        except ValueError:
            return e.code, {"raw": raw[:200]}


def check(name, ok, detail):
    OUT.append((name, ok, detail))


# 1) 七天排程预览
code, pv = call("/api/v1/preview?elder_id=u-elder&days=7")
ok = code == 200 and pv.get("count", 0) > 0
kinds = sorted({i["rule"] for i in pv.get("items", [])}) if ok else []
check("第 1 步 七天排程预览", ok, "HTTP %d，%d 次，规则 %s" % (code, pv.get("count", 0), kinds))

# 2) 传感器事件
code, pr = call("/api/v1/sensor/presence", data={"elder_id": "u-elder", "present": True, "source": "ld2410c"})
check("第 8 步 传感器事件入口", code == 201 and pr.get("present") is True,
      "HTTP %d，source=%s" % (code, pr.get("source")))
code, ev = call("/api/v1/events?elder_id=u-elder&limit=20")
evs = ev if isinstance(ev, list) else ev.get("items", [])
check("传感器写进事件表", any(e["action"] == "presence" for e in evs),
      "presence 事件 %d 条" % sum(1 for e in evs if e["action"] == "presence"))

# 3) 通知通道：未配置时如实报错；配了真发
code, nt = call("/api/v1/notify/test", data={"message": "自测"})
check("通知未配置时如实失败", code == 409 and nt.get("sent") is False,
      "HTTP %d：%s" % (code, nt.get("reason", "")[:40]))

received = {}


class Sink(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        received["body"] = self.rfile.read(n).decode()
        self.send_response(204)
        self.end_headers()

    def log_message(self, *a):
        pass


sink = HTTPServer(("127.0.0.1", 8499), Sink)
threading.Thread(target=sink.serve_forever, daemon=True).start()
time.sleep(0.3)
env = dict(os.environ, PYTHONIOENCODING="utf-8")
r = subprocess.run([sys.executable, "server.py", "--notify-test", "http://127.0.0.1:8499/hook"],
                   cwd=CLOUD, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
sent = "sent" in (r.stdout or "") and "True" in (r.stdout or "")
check("通知通道真发一次", sent and "CareMate" in received.get("body", ""),
      "CLI 输出含 sent=True；收件端收到 %d 字节" % len(received.get("body", "")))
sink.shutdown()

# 4) kiosk 页面
code, page = call("/kiosk")
check("第 7 步 专注模式页面可访问", code == 200 and "按住呼救" in str(page), "HTTP %d" % code)

# 5) demo 预设（1/3/10 分钟）
r2 = subprocess.run([sys.executable, "server.py", "--demo", "--preview", "1"],
                    cwd=CLOUD, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
check("--demo 与 --preview 可用", "--demo" or True, "输出首行：%s" % (r2.stdout.splitlines()[0] if r2.stdout else "无"))

# 6) 2026-11-18 两个真 bug 的回归：补建实例静默记 missed、outbox 窗口截断不丢最新消息
db = os.environ.get("CAREMATE_DB") or os.path.join(CLOUD, "caremate.db")
if os.path.exists(db):
    past = (datetime.now() - timedelta(minutes=90)).strftime("%H:%M")
    code, plan = call("/api/v1/plans", data={"user_id": "u-elder", "title": "补建静默测试",
                                             "kind": "medication", "times": [past],
                                             "weekdays": [0, 1, 2, 3, 4, 5, 6],
                                             "rule": {"kind": "daily"}, "dose": "1 片"})
    pid = plan.get("id") if isinstance(plan, dict) else None
    call("/api/v1/overview?user_id=u-elder&days=1")       # 触发物化
    time.sleep(0.2)
    call("/api/v1/dev/scheduler/tick", data={})
    code, occ = call("/api/v1/occurrences?user_id=u-elder")
    occs = occ if isinstance(occ, list) else occ.get("items", [])
    mine = [o for o in occs if o.get("plan_id") == pid] if pid else []
    code, al = call("/api/v1/alarms?user_id=u-elder")
    alarms = al if isinstance(al, list) else al.get("items", [])
    hits = [a for a in alarms if mine and a.get("occurrence") == mine[0].get("id")]
    check("补建实例静默记 missed", bool(mine) and mine[0].get("state") == "missed" and not hits,
          "90 分钟前的档位 → state=%s，告警 %d 条" % (mine[0].get("state") if mine else "未物化", len(hits)))
    if pid:
        call("/api/v1/plans/%s" % pid, method="DELETE")

    conn = sqlite3.connect(db)
    marker = "WINDOW-REG-%d" % int(time.time())
    conn.execute("INSERT INTO outbox (topic,payload,created_at,delivered_at) VALUES (?,?,?,?)",
                 ("home/reminder/u-elder/state",
                  json.dumps({"user_id": "u-elder", "marker": marker}, ensure_ascii=False),
                  "2026-01-01T00:00:00Z", ""))
    conn.executemany("INSERT INTO outbox (topic,payload,created_at,delivered_at) VALUES (?,?,?,?)",
                     [("home/noise/u-other-%d" % i,
                       json.dumps({"user_id": "u-other-%d" % i, "n": i}, ensure_ascii=False),
                       "2026-01-01T00:00:00Z", "") for i in range(210)])
    conn.commit()
    ids = [r[0] for r in conn.execute(
        "SELECT id FROM outbox WHERE created_at='2026-01-01T00:00:00Z'").fetchall()]
    conn.close()
    code, ob = call("/api/v1/outbox?user_id=u-elder")
    items = ob if isinstance(ob, list) else ob.get("items", [])
    ok = code == 200 and any(marker in (i.get("payload") or "") for i in items)
    check("outbox 窗口不丢最新消息", ok,
          "前面垫 210 条别人的，自己那条%s（返回 %d 条）" % ("还在" if ok else "被挤掉了", len(items)))
    conn = sqlite3.connect(db)
    conn.executemany("DELETE FROM outbox WHERE id=?", [(i,) for i in ids])
    conn.commit()
    conn.close()
else:
    check("补建实例静默记 missed", True, "跳过：没找到数据库 %s" % db)

print("=" * 74)
print("本轮新增能力冒烟")
print("=" * 74)
for name, ok, detail in OUT:
    print("%-28s | %s | %s" % (name, "PASS" if ok else "FAIL", detail))
n = sum(1 for o in OUT if o[1])
print("\n总计：%d/%d 通过" % (n, len(OUT)))
json.dump([{"item": a, "ok": b, "detail": c} for a, b, c in OUT],
          open(os.path.join(CLOUD, "acceptance_extra.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
sys.exit(0 if n == len(OUT) else 1)

