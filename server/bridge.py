# -*- coding: utf-8 -*-
# 作用：MQTT 桥：把 outbox 里的事件用零依赖 MQTT 3.1.1 客户端 publish 到 broker，再标记已消费；并订阅 home/sensor/presence 把雷达上报转成一次 HTTP POST
"""CareMate MQTT 桥：把服务端 outbox 里的事件发到 mosquitto（树莓派/香橙派上跑）。

为什么自己写：这台机器没有 paho-mqtt，而且目标板子上也不想装依赖。
这里只实现 MQTT 3.1.1 的 CONNECT / SUBSCRIBE(QoS0) / PUBLISH(QoS0) / PINGREQ，够用。

两个方向：
    下行（服务端 → 家里）：拉 outbox → publish → 标记已消费
    上行（家里 → 服务端）：订阅 home/sensor/presence → POST /api/v1/sensor/presence
                           （没有这一步，雷达数据到不了服务端，「久未活动」告警就没有输入）

用法：
    python bridge.py --host 192.168.1.50 --port 1883 --once      # 跑一轮（含一次 presence 接收）
    python bridge.py --host 127.0.0.1 --api http://127.0.0.1:8000 # 常驻
    python bridge.py --dry-run --once                            # 不连 broker，只打印报文

topic 约定（与 4.2.3 一致）：
    home/reminder/{user}/state   实例状态变化
    home/record/{user}           新记录
    home/alarm/{user}            告警（含 SOS、升级、久未活动）
    home/sensor/presence         传感器上报（ESP32 发布，本桥**订阅并转发**成 HTTP）
    home/sensor/presence/seen    服务端收到 presence 后的回显（本桥不订阅，避免自己转自己）

注意：服务端的回显必须用 /seen 这个子 topic。如果回显也写 home/sensor/presence，
桥会把服务端刚写进去的 presence 再 POST 一遍，形成无限回环。
"""

import argparse
import json
import socket
import struct
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "http://127.0.0.1:8000"
TOKEN = "fam-demo-2026"
PRESENCE_TOPIC = "home/sensor/presence"


# ---------------------------------------------------------------- MQTT 编码
# 函数 _utf8：MQTT 字符串字段（两字节长度 + UTF-8 内容）
def _utf8(s):
    raw = s.encode("utf-8")
    return struct.pack("!H", len(raw)) + raw


# 函数 _remaining：MQTT 剩余长度字段的变长编码
def _remaining(n):
    out = b""
    while True:
        byte = n % 128
        n //= 128
        if n:
            out += bytes([byte | 0x80])
        else:
            return out + bytes([byte])


# 函数 pkt_connect：构造 CONNECT 报文（协议名/级别/keepalive/clientId）
def pkt_connect(client_id="caremate-bridge", keepalive=60):
    var = _utf8("MQTT") + bytes([0x04, 0x02]) + struct.pack("!H", keepalive)
    payload = _utf8(client_id)
    body = var + payload
    return b"\x10" + _remaining(len(body)) + body


# 函数 pkt_publish：构造 PUBLISH 报文（QoS0，topic + payload）
def pkt_publish(topic, payload):
    if isinstance(payload, (dict, list)):
        payload = json.dumps(payload, ensure_ascii=False)
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    body = _utf8(topic) + payload
    return b"\x30" + _remaining(len(body)) + body


# 函数 pkt_subscribe：构造 SUBSCRIBE 报文（QoS0，单个 topic filter）
def pkt_subscribe(topic, packet_id=1):
    body = struct.pack("!H", packet_id) + _utf8(topic) + bytes([0x00])
    return b"\x82" + _remaining(len(body)) + body


# 函数 pkt_pingreq：构造心跳报文
def pkt_pingreq():
    return b"\xc0\x00"


# 函数 pkt_disconnect：构造断开报文
def pkt_disconnect():
    return b"\xe0\x00"


# ---------------------------------------------------------------- 收报文
# 函数 _recv_exact：读满 n 字节（broker 的报文可能被拆成多次 TCP 包）
def _recv_exact(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("broker 断开了连接")
        buf += chunk
    return buf


# 函数 read_packet：读一个完整 MQTT 报文，返回 (首字节, 报文体)
def read_packet(sock, timeout=1.0):
    sock.settimeout(timeout)
    head = _recv_exact(sock, 1)[0]
    value, mult = 0, 1
    for _ in range(4):
        b = _recv_exact(sock, 1)[0]
        value += (b & 0x7F) * mult
        if not b & 0x80:
            break
        mult *= 128
    return head, _recv_exact(sock, value) if value else b""


# 函数 parse_publish：从 PUBLISH 报文里取出 (topic, payload)
def parse_publish(head, body):
    qos = (head >> 1) & 0x03
    tlen = struct.unpack("!H", body[:2])[0]
    topic = body[2:2 + tlen].decode("utf-8", "replace")
    rest = body[2 + tlen + (2 if qos else 0):]        # QoS>0 时多两个字节的 packet id
    return topic, rest


# ---------------------------------------------------------------- 简单客户端
class Mqtt:
    # 函数 __init__：保存 broker 地址与 dry-run 标记
    def __init__(self, host, port=1883, client_id="caremate-bridge", dry_run=False):
        self.host, self.port = host, port
        self.client_id = client_id
        self.dry_run = dry_run
        self.sock = None
        self.sent = 0
        self.received = 0

    # 函数 connect：建立 TCP 连接并校验 CONNACK 返回码
    def connect(self):
        if self.dry_run:
            return True
        self.sock = socket.create_connection((self.host, self.port), timeout=8)
        self.sock.sendall(pkt_connect(self.client_id))
        head, body = read_packet(self.sock, timeout=5)
        if head >> 4 != 2 or len(body) < 2 or body[1] != 0x00:
            raise ConnectionError("broker 拒绝连接：%r" % (bytes([head]) + body))
        return True

    # 函数 subscribe：订阅一个 topic filter，等 SUBACK
    def subscribe(self, topic=PRESENCE_TOPIC):
        if self.dry_run:
            print("  [dry-run] 订阅 %s（不上报）" % topic)
            return True
        if not self.sock:
            self.connect()
        self.sock.sendall(pkt_subscribe(topic))
        head, body = read_packet(self.sock, timeout=5)
        if head >> 4 != 9:
            raise ConnectionError("SUBACK 异常：%r" % (bytes([head]) + body))
        if len(body) >= 3 and body[2] == 0x80:
            raise ConnectionError("broker 拒绝订阅 %s" % topic)
        return True

    # 函数 publish：发送一条 PUBLISH；失败时重连一次再发
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

    # 函数 poll：等 broker 推来的 PUBLISH，返回 [(topic, payload_bytes)]
    def poll(self, timeout=1.0, limit=20):
        out = []
        if self.dry_run or not self.sock:
            return out
        deadline = time.time() + timeout
        while len(out) < limit:
            left = deadline - time.time()
            if left <= 0:
                break
            try:
                head, body = read_packet(self.sock, timeout=min(left, 0.3))
            except socket.timeout:
                continue
            except ConnectionError:
                self.close()
                break
            ptype = head >> 4
            if ptype == 3:                      # PUBLISH
                topic, payload = parse_publish(head, body)
                out.append((topic, payload))
                self.received += 1
            elif ptype == 13:                   # PINGRESP，忽略
                continue
        return out

    # 函数 ping：发送心跳，保活连接
    def ping(self):
        if self.sock and not self.dry_run:
            try:
                self.sock.sendall(pkt_pingreq())
            except OSError:
                self.close()

    # 函数 close：优雅断开并关闭 socket
    def close(self):
        if self.sock and not self.dry_run:
            try:
                self.sock.sendall(pkt_disconnect())
                self.sock.close()
            except OSError:
                pass
        self.sock = None


# ---------------------------------------------------------------- HTTP
def api_get(path, base=API, token=TOKEN):
    req = urllib.request.Request(base + path, headers={"X-Token": token})
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.loads(r.read().decode() or "{}")


# 函数 api_post：调用后端接口（JSON POST）
def api_post(path, data, base=API, token=TOKEN):
    req = urllib.request.Request(
        base + path, data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json", "X-Token": token}, method="POST")
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.loads(r.read().decode() or "{}")


# 函数 drain：把 outbox 里已发的事件标记为已消费
def drain(base=API, token=TOKEN):
    return api_post("/api/v1/outbox/drain", {}, base, token)


# 函数 forward_presence：把一条 presence 报文转成 POST /api/v1/sensor/presence
def forward_presence(topic, raw, base=API, token=TOKEN, elder="", verbose=True):
    """ESP32 发的是 {"elder_id","present","source","ts"}；这里只取 present 与来源。

    返回 True 表示服务端已收下（201），False 表示报文坏了/请求失败（下一条继续，不阻塞）。
    """
    try:
        data = json.loads((raw or b"").decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        print("[bridge] presence 报文不是 JSON，已忽略：%r" % (raw or b"")[:60])
        return False
    who = data.get("elder_id") or elder
    body = {"present": bool(data.get("present", True)),
            "source": "mqtt:%s" % (data.get("source") or "sensor")}
    path = "/api/v1/sensor/presence" + ("?user=" + urllib.parse.quote(who) if who else "")
    try:
        res = api_post(path, body, base, token)
    except (urllib.error.URLError, OSError) as exc:
        print("[bridge] presence 上报失败（下一条继续）：%s" % exc)
        return False
    if verbose:
        print("[bridge] presence → %s present=%s 服务端:%s"
              % (who or "自己", body["present"], res.get("at") or res))
    return True


# 函数 handle_inbox：收一轮 broker 推来的消息，presence 的转成 HTTP
def handle_inbox(mqtt, base=API, token=TOKEN, elder="", timeout=1.0, presence_topic=PRESENCE_TOPIC):
    handled = 0
    for topic, payload in mqtt.poll(timeout=timeout):
        if topic == presence_topic or topic.startswith(presence_topic + "/"):
            if topic.endswith("/seen"):        # 服务端回显，跳过（防回环）
                continue
            forward_presence(topic, payload, base, token, elder)
            handled += 1
    return handled


# 函数 pump：主循环：拉 outbox → publish → 标记已消费；每轮再收一次 presence
def pump(mqtt, base=API, token=TOKEN, once=False, interval=2.0, verbose=True,
         elder="", presence=True, presence_topic=PRESENCE_TOPIC, inbox_timeout=1.0):
    """下行：把 outbox 里待发的事件逐条发到 broker，发完标记已消费。
    上行：每轮顺带收 broker 推来的 presence，转成一次 HTTP 上报。"""
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
        if presence and not mqtt.dry_run:
            handle_inbox(mqtt, base, token, elder, inbox_timeout, presence_topic)
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
    ap.add_argument("--elder", default="", help="presence 报文里没带 elder_id 时用这个老人账号")
    ap.add_argument("--client-id", default="caremate-bridge")
    ap.add_argument("--once", action="store_true", help="只跑一轮")
    ap.add_argument("--dry-run", action="store_true", help="不连 broker，只打印将要发的报文")
    ap.add_argument("--interval", type=float, default=2.0, help="常驻时的轮询间隔（秒）")
    ap.add_argument("--presence-topic", default=PRESENCE_TOPIC, help="订阅哪个 topic 收传感器上报")
    ap.add_argument("--wait", type=float, default=3.0, help="--once 时等 presence 的秒数")
    ap.add_argument("--no-presence", action="store_true", help="只做下行，不订阅传感器上报")
    args = ap.parse_args()

    mqtt = Mqtt(args.host, args.port, args.client_id, dry_run=args.dry_run)
    want_presence = not args.no_presence
    if not args.dry_run:
        try:
            mqtt.connect()
            print("[bridge] 已连上 broker %s:%d" % (args.host, args.port))
            if want_presence:
                mqtt.subscribe(args.presence_topic)
                print("[bridge] 已订阅 %s（雷达/红外 → 服务端）" % args.presence_topic)
        except (OSError, ConnectionError) as exc:
            print("[bridge] 连不上 broker：%s" % exc)
            print("        树莓派上先装： sudo apt install mosquitto mosquitto-clients")
            return 2
    if args.dry_run and want_presence:
        mqtt.subscribe(args.presence_topic)
    print("[bridge] 服务 %s ｜ 下行 outbox → publish ｜ 上行 %s → HTTP"
          % (args.api, args.presence_topic if want_presence else "（已关闭）"))
    try:
        n = pump(mqtt, args.api, args.token, once=args.once, interval=args.interval,
                 elder=args.elder, presence=want_presence,
                 presence_topic=args.presence_topic,
                 inbox_timeout=args.wait if args.once else 1.0)
    except KeyboardInterrupt:
        print("\n[bridge] 停止")
        n = 0
    finally:
        mqtt.close()
    print("[bridge] 共发出 %d 条，收到 %d 条上行" % (mqtt.sent, mqtt.received))
    return 0


if __name__ == "__main__":
    sys.exit(main())
