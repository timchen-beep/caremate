# 作用：后端说明：接口清单、部署方式、验收命令与设计取舍
# CareMate 云端 + 双入口（v0.5：按 4.2 文档对齐）

## v0.5 改了什么（对照《Opening Report 4.2》）

| 文档条目 | 实现 |
|---|---|
| occurrence 落表 | `occurrences` 表：`due_at`(UTC)、`state`、`level`、`snooze_count`、`notified_at/confirmed_at/missed_at`，`UNIQUE(plan_id,due_at)` |
| 调度器在服务内 | 后台线程每 30 s 扫描：**到点即 `notified`**，迟到 `THRESHOLD_1`（默认 2 分钟）`escalated`（通知家属），`THRESHOLD_3`（默认 15 分钟）`missed`；`CAREMATE_SCHEDULER=0` 可关 |
| 唯一状态入口 | `transition(occ, action, actor, now)`：写 event 与改 state 在同一事务 |
| UTC + 时区 | 库内 UTC（带 Z），`users.tz` 决定展示，API 同时给 `due_at_utc` 与 `due_at_local` |
| 审计 | `events.actor` 记具体账号；看板代确认写 `u-family`，调度器写 `scheduler` |
| 记录追加式更正 | 更正写 revision+1 的新行，旧行 `superseded_by` 指向新行；`?history=1` 可看全历史 |

### 验收（文档 4.2.6，本机实测）

| 检查项 | 实测 | 结论 |
|---|---|---|
| P95 延迟 ≤ 5 s | p50 30 ms / p95 34 ms / p99 35 ms（n=100） | 通过 |
| 断网 3 条回补 | 库里正好 3 条，重放被识别 3 次 | 通过 |
| 10 次强制重启 | 实例数 9 → 9，异常 0 次 | 通过 |
| 跨家庭 / 跨角色 | 社区建计划 403、跨家庭读 403、家属冒充社区 403 | 通过 |
| 升级不依赖页面 | 不碰页面，30 s 内 pending → escalated + level 2 告警 | 通过 |

复现：`python test_accept.py`（结果写 `acceptance.json`）、`python test_auto_scheduler.py`。


一个进程、一个地址、两个入口；服务端按《需求扩展与技术路线》《实现步骤目标》两份文档重写。

```bash
cd caremate-cloud
python server.py --port 8000
```

两种形态，各归其位：

| 形态 | 交付物 | 入口 |
|---|---|---|
| **老人端 = App** | `caremate_app/`（Flutter，`flutter build apk` 出 APK 装到手机） | 手机桌面图标，系统通知触达 |
| **看护端 = Web** | 本目录的 `/dashboard`（浏览器打开，电脑/手机都行） | http://127.0.0.1:8000/dashboard |
| 云端 | 本目录 `server.py` | 两端的共同数据源 |

`/app` 只是**同一套界面的网页预览**，方便在电脑上评审；系统通知、锁屏提醒这类能力的正式答案在 Flutter APK 里。

手机访问：`python server.py --host 0.0.0.0`，手机与电脑同 WiFi，打开 `http://电脑局域网IP:8000/app`。

令牌：老人 `app-elder-001`（绑定码 8823）｜家属 `fam-demo-2026`｜社区 `comm-demo-2026`

## 文档要求 → 实现位置

| 文档条目 | 代码/接口 |
|---|---|
| plan 与 occurrence 分离，改计划不污染历史 | `plans` 表 + `occurrences()` 物化，状态由 `events` 推导 |
| 7 种重复规则 | `plans.rule` JSON：daily / weekly / interval / monthly / course / mealOffset（餐前餐后按饮食记录推导） |
| 状态机 pending→notified→escalated→confirmed/missed | `occurrence_state()`；阈值 `CAREMATE_THRESHOLD_1`（升级家属，默认 2 分钟）与 `THRESHOLD_3`（记未确认，默认 15 分钟） |
| 稍后最多 3 次 | `record_event()`：第 4 次强制转 missed，并写 `snooze_limit` 告警 |
| 记录可纠错、可撤销、留痕 | `records.created_by/updated_by/revision/deleted`；`PATCH` 更正、`DELETE` 逻辑删除 |
| 统计口径要写清 | `stats().caliber`：自然日、分母=已到期实例、漏记算缺失、超时 15 分钟 |
| 断网补传 + 幂等 | `event_id = uuid5(occurrence|action|client_ts)` + `INSERT OR IGNORE` |
| 三角色权限 | `users.role` + `links.can_edit`：社区只读、家属可写、老人只动自己的实例 |
| 社区上报 webhook | `POST /api/v1/community/webhook`（`CAREMATE_WEBHOOK_URL` 配真实地址） |
| MQTT topics | `publish()` → `outbox` 表：`home/reminder/{user}/state`、`home/record/{user}`、`home/alarm/{user}` |
| 导出 CSV | `/api/v1/export.csv?type=records|events|alarms`（带 BOM，Excel 可开） |
| 云成本/可迁移 | 配置全走环境变量；`connect()` 是 SQLite→PostgreSQL 唯一切换点 |

## 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/health`、`/api/v1/version` | 版本、运行模式、已配置的云能力 |
| GET | `/api/v1/overview?date=&days=` | 一次拿全：实例 + 计划 + 记录 + 告警 + 统计（看板全用它） |
| GET/POST | `/api/v1/plans`；`PUT/DELETE /api/v1/plans/{id}` | 计划 CRUD；`{"active":0}` 停用，`{"paused_until":"…"}` 暂停 |
| POST | `/api/v1/occurrences/action` | `{plan_id, slot, action: confirmed\|snoozed\|missed}` |
| POST | `/api/v1/events` | **批量上行**：`{events:[{occurrence_id,action,client_ts,event_id}]}`，逐条返回 accepted/duplicates/rejected（4.1 图第 5 层） |
| GET | `/api/v1/state?since=` | **按游标回灌**：since 之后变化的实例与记录，返回 `next_since`（换机/重装/家属代确认后对齐） |
| POST | `/api/v1/alarm` | **端侧主动告警**：`{kind:sos,note,device}`，立即落库并推给家属端 |
| GET/POST | `/api/v1/records`；`PATCH/DELETE /api/v1/records/{id}` | 记录增改撤 |
| GET | `/api/v1/stats?days=7` | 完成率、连续天数、按日分布、口径说明 |
| GET | `/api/v1/alarms`；`POST /api/v1/alarms/ack` | 告警与已读 |
| POST | `/api/v1/community/webhook` | 社区上报异常事件 |
| GET | `/api/v1/export.csv` | 导出 |
| GET | `/api/v1/outbox`；`POST /api/v1/outbox/drain` | MQTT 桥接的取件/确认 |

## 云服务预留（改这 5 个环境变量就能上云）

```bat
set CAREMATE_DB=postgresql://user:pwd@host:5432/caremate
set CAREMATE_MODE=cloud
set CAREMATE_JWT_SECRET=<随机串>
set CAREMATE_MQTT_URL=mqtt://127.0.0.1:1883
set CAREMATE_WEBHOOK_URL=https://community.example.com/hook
```

- `publish(topic, payload)` 是**唯一**对外出口：本地写 `outbox`，云模式换成 `paho-mqtt.publish` 或 `requests.post` 即可，业务代码不用动。
- 看板「云端」页会显示 MQTT / JWT / Webhook 是否已配置，并给出待发事件列表。

## 实测记录（本机）

```
POST /plans                          201 {"id":"p-…"}
POST /occurrences/action ×4          前 3 次 snoozed，第 4 次 forced_missed=True → missed
同一 client_ts 重复提交               第二次 duplicate=True（幂等）
POST /records → PATCH → DELETE        revision 1→2，deleted=True（留痕）
GET  /stats                          total(due)=3 planned=5 completion=0.333
POST /community/webhook              201；家属越权调用 → 403
GET  /outbox                         6 条待发；drain 标记 6 条已消费
GET  /export.csv?type=records|events|alarms   三份均带 BOM
```

## 还没做的（文档里明确列为 P1/P2 或平台相关）

- 月度 PDF（给医生）——目前只有 CSV；
- 语音播报 / ASR 在 App 端（Flutter 工程里留了位置，Web 端只做浏览器通知）；
- 传感器接入（LD2410C / F1）——接口约定 `home/sensor/presence`，服务端只消费事件；
- 真正的 JWT 签发与刷新——现在是固定令牌，方便演示。

## 老人端"装到桌面"（PWA，无需 APK）

`/app` 已配好 PWA：`manifest.webmanifest` + `sw.js` + 图标（192/512/apple-touch）。

| 平台 | 安装方式 | 效果 |
|---|---|---|
| 安卓 Chrome / Edge | 右上角菜单 →「安装应用 / 添加到主屏幕」 | 桌面图标、全屏无地址栏、离线外壳 |
| iPhone Safari | 底部「分享」→「添加到主屏幕」 | 同上（微信内置浏览器不支持，需先"用浏览器打开"） |

注意三条硬限制：

1. **手机安装要求 HTTPS 或 localhost**：`http://192.168.x.x:8000` 下 Service Worker 不注册，只能加个快捷方式（没有离线缓存）。手机想真装，得先用内网穿透给个 https 链接。
2. **没有系统通知**：PWA 拿不到安卓的精确闹钟，锁屏不会自动弹；只能在打开页面时提醒 + 语音。系统通知的正式答案仍是 Flutter APK。
3. **离线只能打开外壳**：页面能开，但读写数据要连服务端；断网时如实报"离线"。

产物：`web/manifest.webmanifest`、`web/sw.js`、`web/icon-192.png`、`web/icon-512.png`、`web/apple-touch-icon.png`。

## v0.5 P2：配对码换 token / one-off / 部署脚本

| 项 | 实现 | 验收 |
|---|---|---|
| 配对码换 token | `POST /api/v1/auth/pair {code}` → `ses-…` 会话令牌（sessions 表，30 天，只绑一个老人）；`me()` 同时认演示令牌与会话令牌；越界 403；`POST /api/v1/auth/logout` 立即失效 | 9/9（见 `test_p2.py` / `acceptance_p2.json`） |
| one-off 规则 | 规则枚举加 `once` + `rule.date`；看板「一次性（指定某天）」+ 日期框；缺日期 400 | 同左 |
| 部署脚本 | `deploy/`：Caddyfile（自动证书 + 反代）、caremate.service（单进程）、setup.sh（一条命令）、README（systemd/Caddy/验证/成本/上云前必改） | setup.sh 通过 `bash -n` 语法校验；未在真实服务器跑过 |

配对面板在「云端」页，换到的令牌自动写进浏览器 localStorage，右上角令牌框同步更新。

## v0.6：按修订版 4.2 再补六项

| 文档改法 | 代码落点 | 验收 |
|---|---|---|
| P95 拆成「派发延迟 ≤30 s」与「接口 ≤5 s」 | `/api/v1/metrics`：`dispatch = notified_at - due_at`，只统计到期前已物化的实例，补扫单独计数 | p50 27 s / p95 27 s（样本 1，排除 3 条补扫） |
| 事件要能单查询解释 | `events.payload` 写 `prev_state / new_state / level / reason`；新增 `GET /api/v1/occurrences/{id}/events` | 链条 `pending→notified`，一次 GET 返回 |
| 4 位码防枚举 | `/auth/pair` 每地址每分钟 5 次，超出 429 | 六次请求 201×5 → 429 |
| 磁盘满会让提醒停摆 | `ensure_disk()`：低于 `CAREMATE_DISK_MIN_MB`（默认 200）拒绝写入，返回 507 | HTTP 507 |
| 每日在线备份 | `python server.py --backup`（`CAREMATE_BACKUP_DIR` 指目录） | 产出 `caremate-YYYYmmdd-HHMMSS.db` |
| snooze 回流与上限 | 已有：10 分钟回 notified，最多 3 次，第 4 次记 missed（`reason=snooze_limit`） | 见 4.2.6 条目 |

版本号 0.6.0。三套验收：`test_accept.py` 6/6、`test_p2.py` 9/9、`test_v06.py` 7/7。

> **以下为历史变更记录**：仅用于追溯当时的决策，**当前接口以上面的『接口』表为准**。

## v0.7.0：按《接口与实现决策清单》对齐（2026-11-03）

| 清单项 | 结论 | 代码 |
|---|---|---|
| 查某天实例：报告 `GET /occurrences?from=&to=` | 按报告 | 已支持 from/to（含首尾，≤62 天）；`/overview` 保留为一次拿全 |
| 状态变更：报告 `POST /occurrences/{id}/events` | 按报告 | 看板已改用它；`/occurrences/action` 仅 App 兼容 |
| 告警：报告 `GET /alerts` | 按报告 | `/alerts` = 超阈值未确认清单；`/alarms` 只是流水 |
| occurrence 落表 + 历史不变 | 按报告 | 实例行加 `slot_local` 与 `title_snap/dose_snap/kind_snap`，改计划不动历史 |
| 唯一状态入口 | 按报告 | `transition()` 是唯一 `UPDATE occurrences SET state=`（全文件搜得 1 处） |
| UTC + 时区 | 按报告 | 实例身份改用本地墙钟：换时区同一行重算 `due_at`，不新增行 |
| 配对码换 token / 部署脚本 / 一次规则 | 已完成（11-03） | v0.5–v0.6 已实现，见上两节 |

顺带修的真 bug：`ensure_occurrences()` / `occurrences()` 自开连接未提交，事务被回滚——表现是"每次请求都能看到实例、重启就没了"，也让"10 次重启"测试之前是空转通过。现在显式 commit。

四套验收：`test_accept.py` 6/6、`test_p2.py` 9/9、`test_v06.py` 7/7、`test_align.py` 9/9（合计 31/31）。
