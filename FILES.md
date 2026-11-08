# 文件作用（本分支）

> 由各文件头部的「作用：」注释提取；本分支只保留实现代码。

共 36 个文件。

## 后端与页面

| 文件 | 作用 |
|---|---|
| `caremate-cloud/bridge.py` | MQTT 桥：把 outbox 里的事件用零依赖 MQTT 3.1.1 客户端 publish 到 broker，再标记已消费 |
| `caremate-cloud/deploy/Caddyfile` | 反向代理与自动 HTTPS：把域名转发到 127.0.0.1:8000 |
| `caremate-cloud/deploy/README.md` | 部署说明：Caddy + systemd 的单机方案 |
| `caremate-cloud/deploy/caremate.service` | systemd 单元：以单进程跑后端（多进程会有两个调度循环） |
| `caremate-cloud/deploy/setup.sh` | 服务器一键部署：装 Python/tzdata、建 systemd 单元、起服务并用 curl 自检 |
| `caremate-cloud/firmware/esp32_node.ino` | ESP32 传感器节点：读 LD2410C 雷达并上报 presence，收告警按语义表点灯/蜂鸣（不含业务判断） |
| `caremate-cloud/server.py` | CareMate 云端唯一服务：规则展开、实例物化、状态迁移、升级链调度、统计、备份、页面路由（零第三方依赖） |
| `caremate-cloud/start.bat` | Windows 本地启动器：ASCII 输出，避免中文代码页乱码 |
| `caremate-cloud/test_accept.py` | 可靠性验收 6 项：P95 派发、断网补传、越权 403、升级链自驱、10 次重启不丢不重 |
| `caremate-cloud/test_align.py` | 一致性 9 项：from/to 反序 400、改计划历史不变、换时区不新增行、单入口检查 |
| `caremate-cloud/test_auto_scheduler.py` | 调度器手动验证脚本：不碰页面也能自己升级（开发用） |
| `caremate-cloud/test_contract.py` | 契约验收 18 项：鉴权、from/to、事件提交幂等、数组/信封、错误码 |
| `caremate-cloud/test_extra.py` | 新增能力 7 项：七天预览、传感器事件、通知通道、专注模式、--demo/--preview |
| `caremate-cloud/test_p2.py` | 令牌与权限 9 项：配对换令牌、越权访问、一次性规则、角色边界 |
| `caremate-cloud/test_steps.py` | 交互 7 项：呼救、5 秒撤销、记录撤销留痕、久未活动、专注模式页 |
| `caremate-cloud/test_v06.py` | 工程性 7 项：派发延迟、限流 429、磁盘水位 507、备份、单实例保护 |
| `caremate-cloud/web/app.html` | 老人端网页/PWA：大字高对比、语音播报、长按呼救、确认/稍后、记录与自检 --> --> |
| `caremate-cloud/web/apple-touch-icon.png` | iOS 主屏图标 |
| `caremate-cloud/web/dashboard.html` | 家属看板：5 秒刷新今日进度、长轮询收告警弹红条、计划/记录/告警/统计/云端五个分区 --> --> |
| `caremate-cloud/web/icon-192.png` | PWA 图标 192×192 |
| `caremate-cloud/web/icon-512.png` | PWA 图标 512×512 |
| `caremate-cloud/web/index.html` | 落地页：介绍与入口（/app、/dashboard、/kiosk） --> --> |
| `caremate-cloud/web/kiosk.html` | 专注模式页面：四个大按钮，长按左上角 5 秒退出 --> --> |
| `caremate-cloud/web/manifest.webmanifest` | PWA 清单：名称、图标、显示方式 |
| `caremate-cloud/web/sw.js` | Service Worker：缓存静态页，让老人端可离线打开 |

## Flutter 老人端

| 文件 | 作用 |
|---|---|
| `caremate_app/lib/api.dart` | HTTP 客户端：Bearer 令牌、JSON 编解码、错误码到中文提示的映射 |
| `caremate_app/lib/main.dart` | App 入口：初始化状态与本地通知，挂三个 tab（今天/记录/我的） |
| `caremate_app/lib/models.dart` | 数据模型：Occurrence / Plan / AppEvent，字段与契约 v0.1 一一对应 |
| `caremate_app/lib/notify.dart` | 本地通知：通知渠道、按计划重排精确闹钟（setExactAndAllowWhileIdle）、开机重排 |
| `caremate_app/lib/screens/records.dart` | 记录页：今日统计、今天要做的事、已提交动作（含未同步标记） |
| `caremate_app/lib/screens/settings.dart` | 我的页：服务器地址与令牌、配对码、通知自检、同步状态 |
| `caremate_app/lib/screens/today.dart` | 今天页：到点卡片 + 吃了/等会儿/没做 三个大按钮 |
| `caremate_app/lib/state.dart` | 全局状态与动作：拉计划、点确认/稍后、离线队列落盘、联网补传、同步 |
| `caremate_app/pubspec.yaml` | Flutter 依赖：flutter_local_notifications、timezone、shared_preferences、http |

## （根目录）

| 文件 | 作用 |
|---|---|
| `README.md` | 本分支说明：核心文件速览、怎么跑、哪些部分尚未验证 |

<!-- 文件：FILES.md -->
