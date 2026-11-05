# topic 与 payload（与报告 4.2.3 一致）

| topic | 发布方 | 订阅方 | payload |
|---|---|---|---|
| `home/reminder/{user}/state` | 服务端 | Qt 端 / ESP32 | `occurrence, plan_id, due_at, action, state, actor, event_id` |
| `home/record/{user}` | 服务端 | 看板（可选） | `id, type, occurred_at` |
| `home/alarm/{user}` | 服务端 | Qt 端 / ESP32 / 看板 | `id, kind(sos/missed/escalated/inactivity), level, occurrence, message` |
| `home/sensor/presence` | ESP32 | 服务端（经桥） | `elder_id, present(bool), source, ts` |
| `home/terminal/ack` | 带屏终端 | 服务端 | `occurrence, action` |

## 方向与频率

- 服务端 → 设备：事件驱动（状态变化才发），不心跳刷屏。
- 设备 → 服务端：ESP32 状态变化时发，另每 60 秒发一次心跳（防"没消息=没人"的误判）。
- QoS 0 足够：丢了以后端状态为准；真要可靠投递改 QoS1 + 持久会话。

## 桥的职责（`pi/bridge.py`）

后端只写 `outbox` 表，桥负责：

1. `GET /api/v1/outbox` 取待发事件；
2. 逐条 `PUBLISH` 到 broker；
3. `POST /api/v1/outbox/drain` 标记已消费。

桥挂了不丢消息（还在 outbox）；重复发也无害（`event_id` 去重）。
