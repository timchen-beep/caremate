<!-- 作用：函数索引：每个函数一行说明（由代码里的「函数 xxx：…」注释生成，勿手改） -->
# 函数索引（148 个）

| 文件 | 函数 | 说明 |
|---|---|---|
| `app/lib/api.dart` | `_get` | GET 封装：带 Bearer、超时、错误码映射 |
| `app/lib/api.dart` | `_send` | 写操作封装（POST/PATCH）：序列化 + 错误处理 |
| `app/lib/api.dart` | `fetchStateSince` | 按游标回灌服务端状态（4.1 架构图第 5 层下行） |
| `app/lib/api.dart` | `pushEventsBatch` | 批量上行本地事件队列（4.1 架构图第 5 层上行） |
| `app/lib/main.dart` | `build` | 构建界面（App 外层 / 首页外壳） |
| `app/lib/main.dart` | `build` | 构建界面（App 外层 / 首页外壳） |
| `app/lib/main.dart` | `dispose` | 释放控制器与计时器 |
| `app/lib/main.dart` | `initState` | 启动时初始化状态与本地通知 |
| `app/lib/notify.dart` | `showReminder` | 端上调度器到点时弹一条提醒（不依赖服务器） |
| `app/lib/screens/records.dart` | `build` | 记录页：今日统计 + 今天要做的事 + 已提交动作 |
| `app/lib/screens/settings.dart` | `_loadMe` | 拉取当前账号信息（角色、绑定老人） |
| `app/lib/screens/settings.dart` | `build` | 我的页布局：服务器/令牌、配对、通知自检、同步状态 |
| `app/lib/screens/settings.dart` | `dispose` | 释放输入框控制器 |
| `app/lib/screens/settings.dart` | `initState` | 读取已保存的服务器地址与令牌 |
| `app/lib/screens/today.dart` | `_bigButton` | 主操作按钮（吃了/等会儿），84 高、30 号字 |
| `app/lib/screens/today.dart` | `_dangerButton` | 次要操作按钮（这次没做），红框，弱化视觉 |
| `app/lib/screens/today.dart` | `_eventRow` | 动作流水行：标题 + 状态 + 未同步标记 |
| `app/lib/screens/today.dart` | `_reminderCard` | 到点卡片：标题、计划时间、迟到分钟 |
| `app/lib/screens/today.dart` | `build` | 今天页布局：到点卡片 + 三个大按钮 + 今日列表 |
| `app/lib/state.dart` | `_persist` | 把待同步队列与设置写入本地存储（断网也不丢） |
| `app/lib/state.dart` | `pair` | 用配对码换取令牌 |
| `app/lib/state.dart` | `saveSettings` | 保存服务器地址/令牌并立即重新同步 |
| `app/lib/state.dart` | `todayEvents` | 筛选出今天的动作记录 |
| `qt/core/ReminderModel.cpp` | `applyRemoteOccurrences` | /v1/state 的实例直接替换本地清单（服务端为准） |
| `qt/core/ReminderModel.cpp` | `applyRemotePlans` | /v1/plans 的 rule（四种）→ 内部 Rule，再重建实例列表 |
| `qt/core/ReminderModel.cpp` | `confirm` | 确认完成（对应后端 confirmed） |
| `qt/core/ReminderModel.cpp` | `doneCount` | 今日已完成条数 |
| `qt/core/ReminderModel.cpp` | `isoLocal` | datetime → 'yyyy-MM-dd HH:mm'，实例的唯一时刻身份 |
| `qt/core/ReminderModel.cpp` | `loadDemo` | 写入演示规则（用药/喝水/散步） |
| `qt/core/ReminderModel.cpp` | `loadFromStoreOrDemo` | 冷启动读库；库里没数据才写演示规则 |
| `qt/core/ReminderModel.cpp` | `localDbPath` | 本地库路径（设置页/排障用） |
| `qt/core/ReminderModel.cpp` | `markEventsSent` | 把服务端回执的 server_seq 写回本地事件 |
| `qt/core/ReminderModel.cpp` | `matches` | 判断某条规则在某天是否生效（每天/每周/间隔/一次） |
| `qt/core/ReminderModel.cpp` | `missed` | 标记这次没做（对应后端 missed） |
| `qt/core/ReminderModel.cpp` | `pendingEvents` | 还没拿到 server_seq 的事件 |
| `qt/core/ReminderModel.cpp` | `persistNow` | 把规则/实例/事件整表写进 SQLite（单事务） |
| `qt/core/ReminderModel.cpp` | `queueEvent` | 把一次动作记进待上传队列（eventId 固定，重试不变） |
| `qt/core/ReminderModel.cpp` | `rebuild` | 规则 → 未来三天实例列表 |
| `qt/core/ReminderModel.cpp` | `recompute` | 按当前时间算出到期列表与今日列表 |
| `qt/core/ReminderModel.cpp` | `refresh` | 30 秒定时重算（与后端调度节奏一致） |
| `qt/core/ReminderModel.cpp` | `setState` | 改实例状态并发出变更信号 |
| `qt/core/ReminderModel.cpp` | `setSyncState` | 同步状态透给界面（offline / idle / syncing / error） |
| `qt/core/ReminderModel.cpp` | `snooze` | 稍后再提醒，超过次数记为未确认 |
| `qt/core/ReminderModel.cpp` | `sos` | 触发呼救（由界面层发出请求） |
| `qt/core/ReminderModel.cpp` | `touchPersist` | 变更后 1 秒防抖落盘 |
| `scripts/50-verify-system.sh` | `bad` | 打印失败项并累加失败计数 |
| `scripts/50-verify-system.sh` | `ok` | 打印通过项并累加通过计数 |
| `server/bridge.py` | `__init__` | 保存 broker 地址与 dry-run 标记 |
| `server/bridge.py` | `_remaining` | MQTT 剩余长度字段的变长编码 |
| `server/bridge.py` | `api_post` | 调用后端接口（JSON POST） |
| `server/bridge.py` | `close` | 优雅断开并关闭 socket |
| `server/bridge.py` | `connect` | 建立 TCP 连接并校验 CONNACK 返回码 |
| `server/bridge.py` | `drain` | 把 outbox 里已发的事件标记为已消费 |
| `server/bridge.py` | `ping` | 发送心跳，保活连接 |
| `server/bridge.py` | `pkt_connect` | 构造 CONNECT 报文（协议名/级别/keepalive/clientId） |
| `server/bridge.py` | `pkt_disconnect` | 构造断开报文 |
| `server/bridge.py` | `pkt_pingreq` | 构造心跳报文 |
| `server/bridge.py` | `pkt_publish` | 构造 PUBLISH 报文（QoS0，topic + payload） |
| `server/bridge.py` | `publish` | 发送一条 PUBLISH；失败时重连一次再发 |
| `server/bridge.py` | `pump` | 主循环：拉 outbox → publish → drain |
| `server/server.py` | `_ack_open_alarms` | 把该实例所有未处理告警标记为已处理 |
| `server/server.py` | `_alarm_once` | 同一实例的同级告警只发一次，避免刷屏 |
| `server/server.py` | `_alarm_view` | 告警对外视图 |
| `server/server.py` | `_delete` | DELETE 的具体处理（删记录/删计划） |
| `server/server.py` | `_dispatch` | 路由分发：按方法 + 路径前缀匹配到具体处理 |
| `server/server.py` | `_export` | 导出 CSV（按月/按人） |
| `server/server.py` | `_fail` | 统一错误响应（含 code / error 字段） |
| `server/server.py` | `_need_edit` | 写操作权限校验：老人只能动自己的，家属/社区按角色限制 |
| `server/server.py` | `_patch` | PATCH 的具体处理（改记录、暂停计划等） |
| `server/server.py` | `_plan_view` | 计划对外视图 |
| `server/server.py` | `_put` | PUT 的具体处理（改计划等） |
| `server/server.py` | `_qi` | 取查询参数里的整数（缺省/非法/超范围都不报错，按默认值并夹到区间内） |
| `server/server.py` | `_record_view` | 记录对外视图 |
| `server/server.py` | `add_record` | 新增一条记录并写事件审计 |
| `server/server.py` | `apply_token_overrides` | 已存在的库也跟随环境变量换令牌（换令牌不用删库） |
| `server/server.py` | `body_json` | 读取请求体并解析 JSON，空体返回 {} |
| `server/server.py` | `can_view` | 越权判断：能否查看目标老人的数据 |
| `server/server.py` | `cols` | 取表的列名集合，用于加列式迁移 |
| `server/server.py` | `connect` | 打开 SQLite 连接：WAL、忙等超时、行工厂 |
| `server/server.py` | `correct_record` | 纠正记录：追加新版本，旧版本标记 superseded_by |
| `server/server.py` | `delete_record` | 撤销记录：30 分钟窗口内可撤，留下撤销痕迹 |
| `server/server.py` | `do_DELETE` | HTTP DELETE 入口 |
| `server/server.py` | `do_GET` | HTTP GET 入口 |
| `server/server.py` | `do_OPTIONS` | CORS 预检请求 |
| `server/server.py` | `do_PATCH` | HTTP PATCH 入口 |
| `server/server.py` | `do_POST` | HTTP POST 入口 |
| `server/server.py` | `do_PUT` | HTTP PUT 入口 |
| `server/server.py` | `do_backup` | 用 SQLite 在线备份生成一致快照 |
| `server/server.py` | `ensure_disk` | 磁盘剩余空间检查：低于阈值返回 507，避免写坏数据库 |
| `server/server.py` | `inactivity_check` | 长时间无互动且无传感器活动 → 通知家属 |
| `server/server.py` | `ingest_presence` | 传感器上报有人/无人，写事件并影响久未活动判断 |
| `server/server.py` | `init_db` | 建表 + 迁移 + 首次写入演示账号与示例计划 |
| `server/server.py` | `iso` | datetime → ISO 字符串（UTC，秒级） |
| `server/server.py` | `json` | 发送 JSON 响应（自动序列化，保留中文） |
| `server/server.py` | `link_of` | 查家属与老人的绑定关系（越权判断的基础） |
| `server/server.py` | `list_records` | 记录列表，可选带修订历史 |
| `server/server.py` | `load_dotenv` | 读 server/.env（不存在就跳过）。 |
| `server/server.py` | `local_dt` | UTC ISO → 本地时区 datetime（读展示用） |
| `server/server.py` | `local_str` | UTC ISO → 本地 'YYYY-MM-DD HH:MM'（页面与日志用） |
| `server/server.py` | `log_message` | 访问日志：方法、路径、耗时 |
| `server/server.py` | `main` | 命令行入口：参数解析、启动 HTTP 服务与调度线程 |
| `server/server.py` | `meal_slots` | 就餐相关提醒（餐前 30 分钟等）的时刻计算 |
| `server/server.py` | `minutes_since` | 距某个 UTC 时刻过了多少分钟（判断升级/超时） |
| `server/server.py` | `normalize_weekdays` | 星期写法归一：Mon/mon/1 → 1..7 列表 |
| `server/server.py` | `notify` | 外部通知通道（Webhook），未配置时如实报 409 |
| `server/server.py` | `occ_row` | 按实例 id 取一行，不存在返回 None |
| `server/server.py` | `occurrences` | 按区间查实例（老人端/家属端共用） |
| `server/server.py` | `pair_rate_limited` | 配对接口限速（按 IP，每分钟若干次） |
| `server/server.py` | `parse_iso` | 宽松解析客户端传来的 ISO 时间串，失败返回 None |
| `server/server.py` | `pct` | 百分比计算，除零返回 0 |
| `server/server.py` | `plan_times` | 取计划的提醒时刻列表（已归一成 HH:MM） |
| `server/server.py` | `publish` | 把事件写进 outbox（MQTT 桥和长轮询从这里取） |
| `server/server.py` | `raise_alarm` | 生成一条告警：写库 + 入 outbox + 触发通知 |
| `server/server.py` | `scheduler_loop` | 后台调度线程，按 TICK 周期跑 scheduler_tick |
| `server/server.py` | `scheduler_tick` | 每 30 秒扫一次到期实例——到点置 notified，迟到 THRESHOLD_1 置 escalated（通知家属），迟到 THRESHOLD_2 再发一条 level 3 告 |
| `server/server.py` | `send_body` | 统一响应输出：CORS 头、内容类型、长度 |
| `server/server.py` | `slots_on` | 某天某计划应产生的全部提醒时刻（含餐前偏移、间隔/每周/一次性规则） |
| `server/server.py` | `sos` | 呼救：建告警 + 立即推给家属端（<1 秒到达） |
| `server/server.py` | `static` | 静态文件服务（web/ 下的页面与资源） |
| `server/server.py` | `sync_alarm_up` | 端侧直接上报告警（呼救），不等调度器 |
| `server/server.py` | `sync_events_up` | 手机端批量上行本地事件队列；每条复用 transition()（不传连接，避免嵌套锁） |
| `server/server.py` | `sync_state_down` | 按游标回灌服务端状态（换机/重装/家属代确认后对齐） |
| `server/server.py` | `today_occurrences` | 今天到未来的实例（老人端首页） |
| `server/server.py` | `transition` | 唯一允许改 occurrences.state 的函数（文档 4.2.5）。 |
| `server/server.py` | `tzinfo` | 当前时区。顺序：系统 tz 库 → 内置规则 → 固定 +08:00 |
| `server/server.py` | `utc_now` | 当前 UTC 时间（带时区），全库时间基准 |
| `server/v1_adapter.py` | `_alarm` | 呼救/告警（occurrence_id 可空，source=manual） |
| `server/v1_adapter.py` | `_ensure_row_seq` | 取某行序号；没有则分配一个（保证 since=0 时能拿到全量） |
| `server/v1_adapter.py` | `_events` | 上报事件（单条或批量），去重 + 走 transition() |
| `server/v1_adapter.py` | `_last_event_id` | 该实例最后一条事件的 id（端上用来判重放） |
| `server/v1_adapter.py` | `_pair` | 6 位配对码 → 令牌（复用 users.bind_code 与 sessions 表） |
| `server/v1_adapter.py` | `_plan_write` | 计划的 POST / PATCH / DELETE（rule 四种 → 本服务 times/weekdays/rule） |
| `server/v1_adapter.py` | `_record_write` | 记录的 POST / PATCH（at 毫秒 → occurred_at 墙钟） |
| `server/v1_adapter.py` | `_resolve_occurrence` | 端上 int64 occurrenceId → 本地 occurrence id |
| `server/v1_adapter.py` | `current_seq` | 当前序号（不递增） |
| `server/v1_adapter.py` | `ensure_tables` | 建适配层自己的三张表（不动业务表） |
| `server/v1_adapter.py` | `handle_body` | 处理 /v1/* 的写请求（body 由调用方解析好传入，避免二次读 rfile） |
| `server/v1_adapter.py` | `handle_get` | 处理 /v1/* 的 GET（返回 True 表示已处理） |
| `server/v1_adapter.py` | `int_id` | 本地字符串 id → 端上 int64（不存在则分配） |
| `server/v1_adapter.py` | `iso_of_ms` | 毫秒时间戳 → UTC ISO（本服务内部存储格式） |
| `server/v1_adapter.py` | `local_id` | 端上 int64 → 本地字符串 id（plan/record 用；occurrence 另有公式） |
| `server/v1_adapter.py` | `ms_of` | ISO/墙钟字符串 → 毫秒时间戳 |
| `server/v1_adapter.py` | `next_seq` | 取下一个单调序号（写操作调用一次） |
| `server/v1_adapter.py` | `occurrence_int_id` | 按端上冻结公式生成 occurrenceId |
| `server/v1_adapter.py` | `occurrence_payload` | occurrences 行 → 端上 occurrence（§3.1 + state_since.json） |
| `server/v1_adapter.py` | `plan_payload` | plans 表行 → 端上 plan（§3.2 + plans_since.json） |
| `server/v1_adapter.py` | `row_seq` | 某行的写入序号；没有就现分配一个（读路径也能做增量） |
| `tools/verify_all.py` | `ensure_server` | 页面检查前确认 8400 上有服务。 |
