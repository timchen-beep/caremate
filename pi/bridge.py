# -*- coding: utf-8 -*-
# 作用：树莓派/香橙派上的 MQTT 桥（与 server/bridge.py 同一实现，按板子部署习惯放置）
"""CareMate MQTT 桥：把服务端 outbox 里的事件发到 mosquitto（树莓派/香橙派上跑）。

为什么自己写：这台机器没有 paho-mqtt，而且目标板子上也不想装依赖。
这里只实现 MQTT 3.1.1 的 CONNECT / PUBLISH(QoS0) / PINGREQ，够用于单向广播。

用法：
    python bridge.py --host 192.168.1.50 --port 1883 --once      # 跑一轮
    python bridge.py --host 127.0.0.1 --api http://127.0.0.1:8000 # 常驻
    python bridge.py --dry-run --once                            # 不连 broker，只打印报文

topic 约定（与 4.2.3 一致）：
    home/reminder/{user}/state   实例状态变化
    home/record/{user}           新记录
    home/alarm/{user}            告警（含 SOS、升级、久未活动）
    home/sensor/presence         传感器上报（由 ESP32 发布，本桥不产生）
    home/terminal/ack            终端确认
"""

import argparse
import json
import socket
import struct
import sys
import time
import urllib.error
import urllib.request

API = "http://127.0.0.1:8000"
TOKEN = "fam-demo-2026"


# ---------------------------------------------------------------- MQTT 编码
def _utf8(s):
    raw = s.encode("utf-8")
    return struct.pack("!H", len(raw)) + raw


def _remaining(n):
    out = b""
    while True:
        byte = n % 128
        n //= 128
        if n:
            out += bytes([byte | 0x80])
        else:
            return out + bytes([byte])


def pkt_connect(client_id="caremate-bridge", keepalive=60):
    var = _utf8("MQTT") + bytes([0x04, 0x02]) + struct.pack("!H", keepalive)
    payload = _utf8(client_id)
    body = var + payload
    return b"\x10" + _remaining(len(body)) + body


def pkt_publish(topic, payload):
    if isinstance(payload, (dict, list)):
        payload = json.dumps(payload, ensure_ascii=False)
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    body = _utf8(topic) + payload
    return b"\x30" + _remaining(len(body)) + body


def pkt_pingreq():
    return b"\xc0\x00"


def pkt_disconnect():
    return b"\xe0\x00"


# ---------------------------------------------------------------- 简单客户端
class Mqtt:
    def __init__(self, host, port=1883, client_id="caremate-bridge", dry_run=False):
        self.host, self.port = host, port
        self.client_id = client_id
        self.dry_run = dry_run
        self.sock = None
        self.sent = 0

    def connect(self):
        if self.dry_run:
            return True
        self.sock = socket.create_connection((self.host, self.port), timeout=8)
        self.sock.sendall(pkt_connect(self.client_id))
        ack = self.sock.recv(4)
        if len(ack) < 4 or ack[0] != 0x20 or ack[3] != 0x00:
            raise ConnectionError("broker 拒绝连接：%r" % ack)
        return True

    def publish(self, topic, payload):
        packet = pkt_publish(topic, payload)
        if self.dry_run:
            preview = packet[:60]
            print("  [dry-run] %-28s %d 字节  %s%s"
                  % (topic, len(packet), preview.hex(" "), "…" if len(packet) > 60 else ""))
        else:
            if not self.sock:
                self.connect()
            try:
                self.sock.sendall(packet)
            except OSError:
                self.close()
                self.connect()
                self.sock.sendall(packet)
        self.sent += 1
        return self.sent

    def ping(self):
        if self.sock and not self.dry_run:
            try:
                self.sock.sendall(pkt_pingreq())
            except OSError:
                self.close()

    def close(self):
        if self.sock and not self.dry_run:
            try:
                self.sock.sendall(pkt_disconnect())
                self.sock.close()
            except OSError:
                pass
        self.sock = None


# ---------------------------------------------------------------- 拉 outbox
def api_get(path, base=API, token=TOKEN):
    req = urllib.request.Request(base + path, headers={"X-Token": token})
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.loads(r.read().decode() or "{}")


def api_post(path, data, base=API, token=TOKEN):
    req = urllib.request.Request(
        base + path, data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json", "X-Token": token}, method="POST")
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.loads(r.read().decode() or "{}")


def drain(base=API, token=TOKEN):
    return api_post("/api/v1/outbox/drain", {}, base, token)


def pump(mqtt, base=API, token=TOKEN, once=False, interval=2.0, verbose=True):
    """把 outbox 里待发的事件逐条发到 broker，发完标记已消费。"""
    total = 0
    while True:
        try:
            items = api_get("/api/v1/outbox", base, token).get("items", [])
        except (urllib.error.URLError, OSError) as exc:
            print("[bridge] 拉不到 outbox：%s" % exc)
            items = []
        for row in items:
            try:
                payload = json.loads(row["payload"]) if isinstance(row["payload"], str) else row["payload"]
            except ValueError:
                payload = row["payload"]
            mqtt.publish(row["topic"], payload)
            total += 1
        if items:
            try:
                drained = drain(base, token)
                if verbose:
                    print("[bridge] 发出 %d 条，标记已消费 %d 条" % (len(items), drained.get("delivered", 0)))
            except (urllib.error.URLError, OSError) as exc:
                print("[bridge] 标记失败（下轮会重发，靠 event_id 去重）：%s" % exc)
        if once:
            return total
        mqtt.ping()
        time.sleep(interval)


def main():
    ap = argparse.ArgumentParser(description="CareMate MQTT 桥（零依赖）")
    ap.add_argument("--host", default="127.0.0.1", help="broker 地址（树莓派/香橙派 IP）")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--api", default=API, help="CareMate 服务地址")
    ap.add_argument("--token", default=TOKEN)
    ap.add_argument("--client-id", default="caremate-bridge")
    ap.add_argument("--once", action="store_true", help="只跑一轮")
    ap.add_argument("--dry-run", action="store_true", help="不连 broker，只打印将要发的报文")
    ap.add_argument("--interval", type=float, default=2.0, help="常驻时的轮询间隔（秒）")
    args = ap.parse_args()

    mqtt = Mqtt(args.host, args.port, args.client_id, dry_run=args.dry_run)
    if not args.dry_run:
        try:
            mqtt.connect()
            print("[bridge] 已连上 broker %s:%d" % (args.host, args.port))
        except (OSError, ConnectionError) as exc:
            print("[bridge] 连不上 broker：%s" % exc)
            print("        树莓派上先装： sudo apt install mosquitto mosquitto-clients")
            return 2
    print("[bridge] 服务 %s ｜ 每轮拉 outbox → publish → 标记已消费" % args.api)
    try:
        n = pump(mqtt, args.api, args.token, once=args.once, interval=args.interval)
    except KeyboardInterrupt:
        print("\n[bridge] 停止")
        n = 0
    finally:
        mqtt.close()
    print("[bridge] 共发出 %d 条" % mqtt.sent)
    return 0


if __name__ == "__main__":
    sys.exit(main())

