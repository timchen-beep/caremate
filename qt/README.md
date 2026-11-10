<!-- 作用：Qt 端骨架说明：它是什么、怎么连后端、与新契约 /v1/* 的对应、验证边界 -->
# Qt 老人端骨架（CareMate）

本目录是 **Qt/QML 参考实现**：验证规则展开、到期判断、大按钮交互与 JNI 精确闹钟。
真正的手机端交付物是另一个仓库（`fspro7967/yiban_android_app`，Qt 6/QML + C++ facade），
两边的**接口契约相同**：都走 `/v1/*`（见 `docs/端上对接_颐伴手机端.md`）。

## 目录

| 路径 | 作用 |
|---|---|
| `main.cpp` | 入口：注册 `ReminderModel`、启动 `SyncPuller` |
| `core/ReminderModel.*` | 规则 → 实例、状态、事件队列（对应后端 `slots_on` / `transition`） |
| `net/HttpClient.*` | 唯一 HTTP 出口（`/v1/*`，令牌与地址解析） |
| `net/SyncPuller.*` | 拉计划/状态、推事件、呼救上报、离线退避 |
| `pages/*.qml` | 今日、记录、家人、SOS 四个页面 |
| `android/` | JNI 精确闹钟（`AlarmBridge`）与清单 |

## 连后端

```bash
export CAREMATE_API=http://127.0.0.1:8400      # 或你电脑的局域网 IP
export CAREMATE_TOKEN=app-elder-001
# 只看离线演示（不连后端）：
CAREMATE_OFFLINE=1 ./appCareMate
```

后端在同一仓库：`server/server.py`（`/api/v1/*` 给看板，`/v1/*` 给手机端，两者同一真相来源）。

## 同步语义（与手机端仓库一致）

| 时机 | 动作 |
|---|---|
| 启动 | `GET /v1/plans?since=0` → `GET /v1/state?since=<cursor>` |
| 每 15 秒 | 有待传事件先 `POST /v1/events`，否则拉状态 |
| 点确认/推迟/未做 | 本地入队（`eventId` 固定）→ 立即上传 → 回执写回 |
| 呼救 | `POST /v1/alarm`（`source=manual`、`level=3`） |

## 验证边界（如实说明）

| 项 | 状态 |
|---|---|
| 后端 `/v1/*` 契约 | ✅ `server/test_v1.py` 9 项自动化 |
| 本目录能否编译 | ❌ 开发机没有 Qt 6.5+/Android kit，**未编译** |
| 真机 JNI 闹钟 | ❌ 未在真机验证 |