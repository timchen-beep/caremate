# -*- coding: utf-8 -*-
# 作用：验证 MQTT 桥的上行（订阅 home/sensor/presence → POST /api/v1/sensor/presence）与防回环，不用真的装 mosquitto
"""test_bridge.py：MQTT 桥自测（假 broker + 假 API，不依赖 mosquitto、不依赖真后端）

覆盖：
 1. 订阅 home/sensor/presence 后，broker 推来的 radar 报文被转成一次
    POST /api/v1/sensor/presence?user=u-elder，body 里 present/source 正确；
 2. 服务端回显 topic home/sensor/presence/seen 被忽略（否则桥会把自己的回显再转一遍，形成回环）；
 3. 报文不是 JSON 时不崩溃、不误发请求；
 4. 下行不受影响：outbox 为空时照常退出 0。

判定：全部通过返回 0，任一失败返回 1（与其它套件一致）。
"""

import json
import os
import socket
import struct
import subprocess
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import bridge

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print("%-46s %s  %s" % (name, "PASS" if ok else "FAIL", detail))
    return ok


# ---------------------------------------------------------------- 假 MQTT broker
class FakeBroker(threading.Thread):
    """只实现本测试需要的一小段 MQTT：CONNECT→CONNACK、SUBSCRIBE→SUBACK、推 PUBLISH、回 PINGRESP。"""

    def __init__(self, pushes):
        super().__init__(daemon=True)
        self.pushes = pushes                     # [(topic, payload)]
        self.srv = socket.socket()
        self.srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.srv.bind(("127.0.0.1", 0))
        self.srv.listen(1)
        self.port = self.srv.getsockname()[1]
        self.subscribed = []
        self.error = ""

    def run(self):
        try:
            conn, _ = self.srv.accept()
            conn.settimeout(15)
            head, _ = bridge.read_packet(conn, timeout=10)
            if head >> 4 != 1:
                self.error = "第一个报文不是 CONNECT"
                return
            conn.sendall(b"\x20\x02\x00\x00")               # CONNACK 成功
            head, body = bridge.read_packet(conn, timeout=10)
            if head >> 4 == 8:                              # SUBSCRIBE
                pid = body[:2]
                tlen = struct.unpack("!H", body[2:4])[0]
                self.subscribed.append(body[4:4 + tlen].decode())
                conn.sendall(b"\x90\x03" + pid + b"\x00")   # SUBACK 授予 QoS0
                for topic, payload in self.pushes:          # 订阅成功后按顺序推上行报文
                    conn.sendall(bridge.pkt_publish(topic, payload))
            while True:                                     # 之后只回 PINGRESP，直到对端关闭
                head, _ = bridge.read_packet(conn, timeout=15)
                if head >> 4 == 12:
                    conn.sendall(b"\xd0\x00")
        except (ConnectionError, socket.timeout, OSError):
            pass
        except Exception as exc:  # noqa: BLE001
            self.error = "%s: %s" % (type(exc).__name__, exc)


# ---------------------------------------------------------------- 假后端
class FakeApi(BaseHTTPRequestHandler):
    posts = []
    outbox_gets = 0

    def log_message(self, *a):        # 静音
        pass

    def do_GET(self):
        FakeApi.outbox_gets += 1
        self._send({"items": []})

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode() or "{}")
        except ValueError:
            body = {}
        q = urllib.parse.urlparse(self.path)
        FakeApi.posts.append({"path": q.path, "query": dict(urllib.parse.parse_qsl(q.query)),
                              "body": body, "token": self.headers.get("X-Token", "")})
        if q.path == "/api/v1/sensor/presence":
            self._send({"user_id": body.get("user_id", ""), "present": body.get("present"),
                        "source": body.get("source"), "at": "2026-11-18T12:00:00Z"}, 201)
        else:
            self._send({"delivered": 0})

    def _send(self, obj, code=200):
        raw = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


# ---------------------------------------------------------------- 起假服务
def start_api():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), FakeApi)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, "http://127.0.0.1:%d" % srv.server_address[1]


def run_bridge(broker_port, api_base, wait=2.5):
    cmd = [sys.executable, "-X", "utf8", "bridge.py",
           "--host", "127.0.0.1", "--port", str(broker_port),
           "--api", api_base, "--token", "t-elder",
           "--once", "--wait", str(wait), "--client-id", "caremate-test"]
    r = subprocess.run(cmd, cwd=os.path.dirname(os.path.abspath(__file__)),
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    return r


# ---------------------------------------------------------------- presence 语义
def check_presence_semantics():
    """雷达上报要分「有人/无人」：有人算动静、无人不算，否则和「独居老人久未动静要报警」相反。"""
    tmp = os.path.join(os.environ.get("TEMP", "."), "test_bridge_presence.db")
    for suffix in ("", "-wal", "-shm"):
        try:
            os.remove(tmp + suffix)
        except OSError:
            pass
    saved = {k: os.environ.get(k) for k in
             ("CAREMATE_DB", "CAREMATE_SKIP_ENV", "CAREMATE_TZ", "CAREMATE_INACTIVITY_HOURS")}
    os.environ.update(CAREMATE_DB=tmp, CAREMATE_SKIP_ENV="1", CAREMATE_TZ="Asia/Shanghai",
                      CAREMATE_INACTIVITY_HOURS="2")
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import server as srv

    srv.init_db()
    now = srv.utc_now()
    old = now - srv.timedelta(hours=5)
    with srv.connect() as conn:
        conn.execute("UPDATE users SET created_at=? WHERE role='elder'", (srv.iso(old),))
        conn.execute("DELETE FROM events")
        conn.execute("DELETE FROM alarms")

    def presence_events():
        with srv.connect() as conn:
            return [r["payload"] for r in conn.execute(
                "SELECT payload FROM events WHERE action='presence' ORDER BY id")]

    srv.ingest_presence("u-elder", False, "ld2410c")
    fired = srv.inactivity_check(now)
    check("雷达报「无人」不算动静（久未活动照报）", fired == 1, "触发 %d 条" % fired)

    with srv.connect() as conn:
        conn.execute("UPDATE events SET at_utc=?", (srv.iso(old),))
        conn.execute("DELETE FROM alarms")
    srv.ingest_presence("u-elder", True, "ld2410c")
    check("同一秒内 true/false 不会互相去重", len(presence_events()) == 2,
          "presence 事件 %d 条" % len(presence_events()))
    fired = srv.inactivity_check(now)
    check("雷达报「有人」算动静（不报久未活动）", fired == 0, "触发 %d 条" % fired)

    with srv.connect() as conn:
        conn.execute("UPDATE events SET at_utc=?", (srv.iso(old),))
    fired = srv.inactivity_check(now)
    check("「有人」也变旧后照样告警", fired == 1, "触发 %d 条" % fired)

    for key, value in saved.items():            # 还原环境，避免影响后面的检查
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    try:
        os.remove(tmp)
    except OSError:
        pass


def main():
    srv, api_base = start_api()
    try:
        pushes = [
            ("home/sensor/presence",
             json.dumps({"elder_id": "u-elder", "present": True,
                         "source": "ld2410c", "ts": 12345})),
            ("home/sensor/presence/seen",                 # 服务端回显：必须被忽略
             json.dumps({"user_id": "u-elder", "present": True, "source": "mqtt:ld2410c"})),
            ("home/sensor/presence", "这不是JSON"),        # 坏报文：忽略且不崩
            ("home/sensor/presence",
             json.dumps({"elder_id": "u-elder", "present": False, "source": "ld2410c"})),
        ]
        broker = FakeBroker(pushes)
        broker.start()

        r = run_bridge(broker.port, api_base)
        time.sleep(0.2)
        posts = [p for p in FakeApi.posts if p["path"] == "/api/v1/sensor/presence"]

        check("桥成功退出", r.returncode == 0,
              (r.stderr.strip().splitlines() or [""])[-1][:70])
        check("订阅了 home/sensor/presence", bridge.PRESENCE_TOPIC in broker.subscribed,
              ",".join(broker.subscribed) or "未收到 SUBSCRIBE")
        check("上行 presence 落成 HTTP 上报（2 条）", len(posts) == 2,
              "实际 %d 条：%s" % (len(posts), [p["body"] for p in posts]))
        if posts:
            check("第一条 present=true 且带老人账号",
                  posts[0]["body"].get("present") is True
                  and posts[0]["query"].get("user") == "u-elder",
                  "query=%s body=%s" % (posts[0]["query"], posts[0]["body"]))
            check("来源标注 mqtt:ld2410c",
                  posts[0]["body"].get("source") == "mqtt:ld2410c",
                  posts[0]["body"].get("source", ""))
            check("第二条 present=false 也被转（人离开了）",
                  posts[-1]["body"].get("present") is False,
                  str(posts[-1]["body"]))
        check("回显 topic（/seen）没有被转回去", len(posts) == 2,
              "若为 3 条说明存在回环风险")
        check("坏报文不崩溃（桥仍正常退出）", r.returncode == 0 and "不是 JSON" in r.stdout,
              "stdout 含提示：%s" % ("不是 JSON" in r.stdout))
        check("下行也照常跑（拉过 outbox）", FakeApi.outbox_gets >= 1,
              "GET /api/v1/outbox %d 次" % FakeApi.outbox_gets)
        check("假 broker 无内部错误", not broker.error, broker.error)
    finally:
        srv.shutdown()

    check_presence_semantics()

    ok = sum(1 for _, passed, _ in RESULTS if passed)
    total = len(RESULTS)
    print("\n总计：%d/%d 通过" % (ok, total))
    return 0 if ok == total else 1


if __name__ == "__main__":
    sys.exit(main())
