# 函数说明（每个函数在干什么）

> 由代码里的 `函数 X：说明` 注释提取；共 113 个函数。

## `app/lib/api.dart`

| 函数 | 作用 |
|---|---|
| `_get` | GET 封装：带 Bearer、超时、错误码映射 |
| `_send` | 写操作封装（POST/PATCH）：序列化 + 错误处理 |

## `app/lib/main.dart`

| 函数 | 作用 |
|---|---|
| `build` | 构建界面（App 外层 / 首页外壳） |
| `dispose` | 释放控制器与计时器 |
| `initState` | 启动时初始化状态与本地通知 |

## `app/lib/screens/records.dart`

| 函数 | 作用 |
|---|---|
| `build` | 记录页：今日统计 + 今天要做的事 + 已提交动作 |

## `app/lib/screens/settings.dart`

| 函数 | 作用 |
|---|---|
| `_loadMe` | 拉取当前账号信息（角色、绑定老人） |
| `build` | 我的页布局：服务器/令牌、配对、通知自检、同步状态 |
| `dispose` | 释放输入框控制器 |
| `initState` | 读取已保存的服务器地址与令牌 |

## `app/lib/screens/today.dart`

| 函数 | 作用 |
|---|---|
| `_bigButton` | 主操作按钮（吃了/等会儿），84 高、30 号字 |
| `_dangerButton` | 次要操作按钮（这次没做），红框，弱化视觉 |
| `_eventRow` | 动作流水行：标题 + 状态 + 未同步标记 |
| `_reminderCard` | 到点卡片：标题、计划时间、迟到分钟 |
| `build` | 今天页布局：到点卡片 + 三个大按钮 + 今日列表 |

## `app/lib/state.dart`

| 函数 | 作用 |
|---|---|
| `_persist` | 把待同步队列与设置写入本地存储（断网也不丢） |
| `pair` | 用配对码换取令牌 |
| `saveSettings` | 保存服务器地址/令牌并立即重新同步 |
| `todayEvents` | 筛选出今天的动作记录 |

## `qt/core/ReminderModel.cpp`

| 函数 | 作用 |
|---|---|
| `confirm` | 确认完成（对应后端 confirmed） |
| `doneCount` | 今日已完成条数 |
| `isoLocal` | datetime → 'yyyy-MM-dd HH:mm'，实例的唯一时刻身份 |
| `loadDemo` | 写入演示规则（用药/喝水/散步） |
| `matches` | 判断某条规则在某天是否生效（每天/每周/间隔/一次） |
| `missed` | 标记这次没做（对应后端 missed） |
| `rebuild` | 规则 → 未来三天实例列表 |
| `recompute` | 按当前时间算出到期列表与今日列表 |
| `refresh` | 30 秒定时重算（与后端调度节奏一致） |
| `setState` | 改实例状态并发出变更信号 |
| `snooze` | 稍后再提醒，超过次数记为未确认 |
| `sos` | 触发呼救（由界面层发出请求） |

## `scripts/50-verify-system.sh`

| 函数 | 作用 |
|---|---|
| `bad` | 打印失败项并累加失败计数 |
| `ok` | 打印通过项并累加通过计数 |

## `server/bridge.py`

| 函数 | 作用 |
|---|---|
| `__init__` | 保存 broker 地址与 dry-run 标记 |
| `_remaining` | MQTT 剩余长度字段的变长编码 |
| `api_post` | 调用后端接口（JSON POST） |
| `close` | 优雅断开并关闭 socket |
| `connect` | 建立 TCP 连接并校验 CONNACK 返回码 |
| `drain` | 把 outbox 里已发的事件标记为已消费 |
| `ping` | 发送心跳，保活连接 |
| `pkt_connect` | 构造 CONNECT 报文（协议名/级别/keepalive/clientId） |
| `pkt_disconnect` | 构造断开报文 |
| `pkt_pingreq` | 构造心跳报文 |
| `pkt_publish` | 构造 PUBLISH 报文（QoS0，topic + payload） |
| `publish` | 发送一条 PUBLISH；失败时重连一次再发 |
| `pump` | 主循环：拉 outbox → publish → drain |

## `server/firmware/esp32_node.ino`

| 函数 | 作用 |
|---|---|
| `loop` | 主循环：重连、读雷达、状态变化才上报 |
| `onMessage` | 收到 MQTT 消息：按语义表点灯/蜂鸣 |
| `publishPresence` | 把雷达状态以 JSON 发布到 home/sensor/presence |
| `reconnect` | 断线重连并订阅 alarm / reminder 两个 topic |
| `setup` | 初始化串口、雷达、WiFi、MQTT 订阅 |

## `server/server.py`

| 函数 | 作用 |
|---|---|
| `_ack_open_alarms` | 把该实例所有未处理告警标记为已处理 |
| `_alarm_once` | 同一实例的同级告警只发一次，避免刷屏 |
| `_alarm_view` | 告警对外视图 |
| `_delete` | DELETE 的具体处理（删记录/删计划） |
| `_dispatch` | 路由分发：按方法 + 路径前缀匹配到具体处理 |
| `_export` | 导出 CSV（按月/按人） |
| `_fail` | 统一错误响应（含 code / error 字段） |
| `_need_edit` | 写操作权限校验：老人只能动自己的，家属/社区按角色限制 |
| `_patch` | PATCH 的具体处理（改记录、暂停计划等） |
| `_plan_view` | 计划对外视图 |
| `_put` | PUT 的具体处理（改计划等） |
| `_record_view` | 记录对外视图 |
| `add_record` | 新增一条记录并写事件审计 |
| `body_json` | 读取请求体并解析 JSON，空体返回 {} |
| `can_view` | 越权判断：能否查看目标老人的数据 |
| `cols` | 取表的列名集合，用于加列式迁移 |
| `connect` | 打开 SQLite 连接：WAL、忙等超时、行工厂 |
| `correct_record` | 纠正记录：追加新版本，旧版本标记 superseded_by |
| `delete_record` | 撤销记录：30 分钟窗口内可撤，留下撤销痕迹 |
| `do_DELETE` | HTTP DELETE 入口 |
| `do_GET` | HTTP GET 入口 |
| `do_OPTIONS` | CORS 预检请求 |
| `do_PATCH` | HTTP PATCH 入口 |
| `do_POST` | HTTP POST 入口 |
| `do_PUT` | HTTP PUT 入口 |
| `do_backup` | 用 SQLite 在线备份生成一致快照 |
| `ensure_disk` | 磁盘剩余空间检查：低于阈值返回 507，避免写坏数据库 |
| `inactivity_check` | 长时间无互动且无传感器活动 → 通知家属 |
| `ingest_presence` | 传感器上报有人/无人，写事件并影响久未活动判断 |
| `init_db` | 建表 + 迁移 + 首次写入演示账号与示例计划 |
| `iso` | datetime → ISO 字符串（UTC，秒级） |
| `json` | 发送 JSON 响应（自动序列化，保留中文） |
| `link_of` | 查家属与老人的绑定关系（越权判断的基础） |
| `list_records` | 记录列表，可选带修订历史 |
| `local_dt` | UTC ISO → 本地时区 datetime（读展示用） |
| `local_str` | UTC ISO → 本地 'YYYY-MM-DD HH:MM'（页面与日志用） |
| `log_message` | 访问日志：方法、路径、耗时 |
| `main` | 命令行入口：参数解析、启动 HTTP 服务与调度线程 |
| `meal_slots` | 就餐相关提醒（餐前 30 分钟等）的时刻计算 |
| `minutes_since` | 距某个 UTC 时刻过了多少分钟（判断升级/超时） |
| `normalize_weekdays` | 星期写法归一：Mon/mon/1 → 1..7 列表 |
| `notify` | 外部通知通道（Webhook），未配置时如实报 409 |
| `occ_row` | 按实例 id 取一行，不存在返回 None |
| `occurrences` | 按区间查实例（老人端/家属端共用） |
| `pair_rate_limited` | 配对接口限速（按 IP，每分钟若干次） |
| `parse_iso` | 宽松解析客户端传来的 ISO 时间串，失败返回 None |
| `pct` | 百分比计算，除零返回 0 |
| `plan_times` | 取计划的提醒时刻列表（已归一成 HH:MM） |
| `publish` | 把事件写进 outbox（MQTT 桥和长轮询从这里取） |
| `raise_alarm` | 生成一条告警：写库 + 入 outbox + 触发通知 |
| `scheduler_loop` | 后台调度线程，按 TICK 周期跑 scheduler_tick |
| `send_body` | 统一响应输出：CORS 头、内容类型、长度 |
| `slots_on` | 某天某计划应产生的全部提醒时刻（含餐前偏移、间隔/每周/一次性规则） |
| `sos` | 呼救：建告警 + 立即推给家属端（<1 秒到达） |
| `static` | 静态文件服务（web/ 下的页面与资源） |
| `today_occurrences` | 今天到未来的实例（老人端首页） |
| `utc_now` | 当前 UTC 时间（带时区），全库时间基准 |

## `server/web/kiosk.html`

| 函数 | 作用 |
|---|---|
| `down` | 按下开始计时（长按左上角退出 / 长按呼救） |
| `due` | 取当前到期的实例 |
| `fire` | 触发动作（呼救或退出专注模式） |
| `tick` | 每秒刷新时钟与到期提醒 |
| `up` | 松开取消计时 |

