<!-- 作用：给第一次看这个仓库的人：项目是什么、代码怎么跑、从哪读起、改功能改哪里 -->
# 导读：第一次看这个项目，从这里开始

这份文档假设你**从没见过 CareMate**。读完大概 15 分钟，你就能看懂代码、跑起来、知道改哪里。

---

## 1. 三十秒看懂这个项目

**给独居老人用的提醒工具**：到点提醒吃药/喝水/睡觉，老人点一下"吃了"就记录下来；
如果一直没点，就升级通知家属；家属打开网页能看到今天的完成情况，呼救 1 秒内在网页上弹红条。

三个角色：

| 角色 | 用的是什么 | 能做什么 |
|---|---|---|
| 老人 | 手机 App（`app/`） | 收到提醒、点确认、一键呼救 |
| 家属 | 浏览器（`server/web/dashboard.html`） | 看进度、看告警、代确认、建计划 |
| 系统 | 云端服务（`server/server.py`） | 生成提醒、判升级、存记录、通知 |

---

## 2. 代码分成四层，一层只干一件事

```
┌────────────────────┐        ┌─────────────────────┐
│  老人端（Flutter）  │        │  家属端（浏览器）    │
│  app/lib/*.dart    │        │  server/web/*.html  │
└─────────┬──────────┘        └──────────┬──────────┘
          │  同一套 JSON 契约（Bearer 令牌）
          ▼                              ▼
┌──────────────────────────────────────────────────┐
│  云端服务：server/server.py（Python 标准库）      │
│  计划 → 实例 → 事件 → 记录；状态只在服务端        │
└─────────┬────────────────────────────────────────┘
          │  outbox 表 → bridge.py → MQTT
          ▼
┌──────────────────────────────────────────────────┐
│  可选外设：树莓派 broker + ESP32 雷达/灯           │
└──────────────────────────────────────────────────┘
```

**最重要的一句话**：状态只在服务端，客户端只负责"显示"和"提交动作"。
这样手机断网、重启、换设备，都不会出现"这条提醒到底做了没做"的分歧。

---

## 3. 四个核心概念（先记住这四个词）

| 词 | 在代码里 | 含义 | 例子 |
|---|---|---|---|
| **plan** | `plans` 表 | 一条计划（规则） | "氨氯地平，每天 08:00 和 20:00" |
| **occurrence** | `occurrences` 表 | 某天某时刻的**一次**提醒（实例） | "今天 08:00 那次" |
| **event** | `events` 表 | 对实例做过的动作（只追加，不改旧行） | "10:03 老人点了确认" |
| **record** | `records` 表 | 生活记录（喝水/睡眠/活动） | "14:20 喝水 200ml" |

为什么要把 plan 和 occurrence 分开：**改了计划，历史不能被改写**。
08:00 那次已经发生了，你把计划改成 09:00，昨天那条仍然是 08:00（`test_align.py` 专门验这条）。

实例的状态词只有这几个：

```
pending ──通知──▶ notified ──确认──▶ confirmed
   │                  │
   │                  ├──稍后──▶ snoozed ──▶ notified
   │                  └──超时──▶ escalated ──▶ missed
   └──无人操作超时──▶ missed
```

---

## 4. 一条完整链路：老人点了一下"吃了"，代码怎么走

这是**整个项目最值得看的一条链路**，从第 1 步跟到第 8 步，你就懂了 80%。

| 步 | 文件 | 函数 | 干了什么 |
|---|---|---|---|
| 1 | `app/lib/screens/today.dart` | 按钮 `onPressed` | 调 `state.record(occ, 'confirmed')` |
| 2 | `app/lib/state.dart` | `record()` | 生成 `event_id`，写入本地队列 |
| 3 | `app/lib/state.dart` | `_persist()` | 队列落盘，**断网也不丢** |
| 4 | `app/lib/state.dart` | `pushPending()` | `POST /api/v1/occurrences/{id}/events` |
| 5 | `server/server.py` | 路由（搜 `occurrences/action`） | 校验令牌与权限 |
| 6 | `server/server.py` | **`transition()`** | **唯一改状态的地方**：写 `events` → 更新 `occurrences.state` → 关告警 → 入 `outbox` |
| 7 | `server/server.py` | `_ack_open_alarms()` | 该实例的告警自动关闭 |
| 8 | `server/web/dashboard.html` | `watchAlarms()` → `incoming()` | 家属网页长轮询收到变化，进度条更新 |

> 想快速验证第 6 步是"唯一入口"：在仓库里搜 `UPDATE occurrences SET`，只会命中 `transition()` 一处。

---

## 5. 目录地图

| 目录 | 一句话 | 先看哪个文件 |
|---|---|---|
| `server/` | 后端 + 老人端网页 + 家属看板 + 验收脚本 | **`server.py`** |
| `app/` | Flutter 老人端（正式交付的 App） | `lib/state.dart` |
| `qt/` | Qt/QML 老人端骨架（对照技术路线用，未编译） | `core/ReminderModel.cpp` |
| `pi/` | 树莓派 / 香橙派部署（mqtt broker + 服务） | `bridge.py` |
| `scripts/` | Android 系统级改造（priv-app、kiosk、自检） | `50-verify-system.sh` |
| `magisk-module/` | 可整模块回滚的 kiosk 定制层 | `service.sh` |
| `device/` | 刷机与回滚 | `flash-lineage.sh` |
| `docs/` | 契约、硬件、云部署、验收清单 | `契约_手机端对接_v0.1.md` |
| `tools/` | 跑验收并生成证据 | `collect_evidence.py` |

两份自动索引（不知道怎么找文件时看它们）：

- **`FILES.md`** —— 每个文件是干什么的
- **`FUNCTIONS.md`** —— 每个函数是干什么的

---

## 6. 建议的阅读顺序（约 2 小时）

| 顺序 | 看什么 | 为什么 |
|---|---|---|
| 1 | `README.md` 的「快速开始」，把服务跑起来 | 先让它动，再谈理解 |
| 2 | `server/server.py` 里的 `init_db()` | 看数据表长什么样（业务全在这几张表里） |
| 3 | `slots_on()` | 规则怎么变成"今天的提醒" |
| 4 | `ensure_occurrences()` | 什么时候把提醒写进库 |
| 4.5 | `app/lib/local_db.dart` / `device_scheduler.dart` | 手机端主副本三表与端上 30 秒 tick（断网也能提醒） |
| 5 | **`transition()`** | 状态怎么变、为什么只能从这里变 |
| 6 | `scheduler_tick()` | 升级链怎么跑：到点 notified → 2 分钟 escalated（通知家属）→ 5 分钟再发一条 level 3 告警 → 15 分钟 missed |
| 7 | `app/lib/state.dart` 的 `record()` → `pushPending()` | 手机端怎么提交、断网怎么补 |
| 8 | `server/web/dashboard.html` 的 `watchAlarms()` | 家属端为什么能 1 秒内看到 |

**别看** `server.py` 里 1800 行之后的 HTTP 分发（`do_GET`/`_dispatch`），那是管道，先跳过。

---

## 7. 常见改动 → 改哪里

| 你想做的事 | 改这里 |
|---|---|
| 改提醒时间怎么算（加规则类型） | `server.py` 的 `slots_on()` |
| 改升级节奏（默认 2/15 分钟） | 环境变量 `CAREMATE_THRESHOLD_1/3`，逻辑在 `scheduler_tick()` |
| 改"稍后"次数上限 | `transition()` |
| 改统计口径（按天算还是 24h） | `stats()` |
| 加一个接口 | `server.py` 路由表（搜 `"/api/v1/`） + 对应处理函数 |
| 改家属看板样子 | `server/web/dashboard.html` |
| 改手机端按钮/流程 | `app/lib/screens/*.dart` + `app/lib/state.dart` |
| 改本地通知文案/时间 | `app/lib/notify.dart` |
| 让设备发消息给系统 | `bridge.py` + `publish()` |

---

## 8. 怎么跑、怎么证明它能跑

```bash
cd server
python3 server.py --port 8000          # 浏览器打开 http://127.0.0.1:8000/dashboard
python3 test_contract.py               # 契约 18 项
python3 test_accept.py                 # 可靠性 6 项（含 10 次重启、断网补传）
python3 test_align.py                  # 一致性 9 项（改计划不改历史、换时区不新增）
```

八套全过会打印 `总计：X/X 通过`。CI（`.github/workflows/ci.yml`）每次 push 都跑这八套。

---

## 9. 名词表

| 词 | 含义 |
|---|---|
| `slot_local` | 实例的"墙上钟时刻"，如 `2026-11-08 08:00`；用它做实例身份，换时区不会多出一行 |
| `due_at` | 实例的 UTC 到期时刻，用于调度计算 |
| `outbox` | 待发消息表，MQTT 桥从这里取，客户端长轮询也从这里取 |
| `event_id` | 客户端生成的动作唯一 id（`occurrence|action|client_ts`），用于幂等去重 |
| `escalated` | 已升级（通知过家属）但老人仍未确认 |
| `superseded_by` | 记录被纠正后，旧版本指向新版本 |

---

## 10. 边界：这些没做或没验证（别以为有）

| 事项 | 真实状态 |
|---|---|
| App 装到真机 | 未验证（APK 已编译签名，锁屏通知与精确闹钟待实测） |
| MQTT 桥连真 broker | 只做过报文级自测 |
| ESP32 烧录 | 未烧录（无硬件） |
| 刷机 / 系统改造脚本 | 未在任何真机执行 |
| 电话/短信通知 | 未接（需要运营商资质），只预留 Webhook |
| 云端部署 | 脚本齐，未在真实服务器跑过 |

---

## 11. 三个设计取舍（答辩会被问）

1. **为什么状态只在服务端**：这是"提醒不丢不重"成立的前提；客户端只提交动作。
2. **为什么 `transition()` 只有一个**：状态变化只有一条路径，才能保证事件日志和实例状态永远一致。
3. **为什么迁移用了 `slot_local` 而不是自增 id**：换时区、重跑调度都不会重复创建实例。