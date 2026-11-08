# 文件作用（本分支）

> 由各文件头部的「作用：」注释提取；二进制与产物在表中注明。

共 60 个文件。

## 后端与页面

| 文件 | 作用 |
|---|---|
| `caremate-cloud/DEMO.md` | 8 分钟演示脚本（六段流程：开机→到点→确认→家属端→呼救→异常） --> |
| `caremate-cloud/README.md` | 后端说明：接口、部署、验收 --> |
| `caremate-cloud/acceptance.json` | 验收报告（测试自动生成，产物） |
| `caremate-cloud/acceptance_align.json` | 验收报告（测试自动生成，产物） |
| `caremate-cloud/acceptance_contract.json` | 验收报告（测试自动生成，产物） |
| `caremate-cloud/acceptance_extra.json` | 验收报告（测试自动生成，产物） |
| `caremate-cloud/acceptance_p2.json` | 验收报告（测试自动生成，产物） |
| `caremate-cloud/acceptance_steps.json` | 验收报告（测试自动生成，产物） |
| `caremate-cloud/acceptance_v06.json` | 验收报告（测试自动生成，产物） |
| `caremate-cloud/backups/caremate-20261105-163759.db` | 数据库快照（二进制） |
| `caremate-cloud/bridge.py` | MQTT 桥：把 outbox 里的事件用零依赖 MQTT 3.1.1 客户端 publish 到 broker，再标记已消费 |
| `caremate-cloud/deploy/Caddyfile` | 反向代理与自动 HTTPS：把域名转发到 127.0.0.1:8000 |
| `caremate-cloud/deploy/README.md` | 部署说明：Caddy + systemd 的单机方案 --> |
| `caremate-cloud/deploy/caremate.service` | systemd 单元：以单进程跑后端（多进程会有两个调度循环） |
| `caremate-cloud/deploy/setup.sh` | 服务器一键部署：装 Python/tzdata、建 systemd 单元、起服务并用 curl 自检 |
| `caremate-cloud/docs/HARDWARE.md` | 硬件接入：香橙派/树莓派/ESP32 分工、接线、topic 表 |
| `caremate-cloud/evidence-验收汇总.md` | 七套验收的汇总证据（由 tools/collect_evidence.py 生成） --> --> |
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
| `caremate-cloud/web/apple-touch-icon.png` | 图片资源 |
| `caremate-cloud/web/dashboard.html` | 家属看板：5 秒刷新今日进度、长轮询收告警弹红条、计划/记录/告警/统计/云端五个分区 --> --> |
| `caremate-cloud/web/icon-192.png` | 图片资源 |
| `caremate-cloud/web/icon-512.png` | 图片资源 |
| `caremate-cloud/web/index.html` | 落地页：介绍与入口（/app、/dashboard、/kiosk） --> --> |
| `caremate-cloud/web/kiosk.html` | 专注模式页面：四个大按钮，长按左上角 5 秒退出 --> --> |
| `caremate-cloud/web/manifest.webmanifest` | PWA 清单：名称、图标、显示方式 |
| `caremate-cloud/web/sw.js` | Service Worker：缓存静态页，让老人端可离线打开 |

## Flutter 老人端

| 文件 | 作用 |
|---|---|
| `caremate_app/README.md` | 本包说明：定位、状态、上手顺序、已知限制 --> |
| `caremate_app/lib/api.dart` | HTTP 客户端：Bearer 令牌、JSON 编解码、错误码到中文提示的映射 |
| `caremate_app/lib/main.dart` | App 入口：初始化状态与本地通知，挂三个 tab（今天/记录/我的） |
| `caremate_app/lib/models.dart` | 数据模型：Occurrence / Plan / AppEvent，字段与契约 v0.1 一一对应 |
| `caremate_app/lib/notify.dart` | 本地通知：通知渠道、按计划重排精确闹钟（setExactAndAllowWhileIdle）、开机重排 |
| `caremate_app/lib/screens/records.dart` | 记录页：今日统计、今天要做的事、已提交动作（含未同步标记） |
| `caremate_app/lib/screens/settings.dart` | 我的页：服务器地址与令牌、配对码、通知自检、同步状态 |
| `caremate_app/lib/screens/today.dart` | 今天页：到点卡片 + 吃了/等会儿/没做 三个大按钮 |
| `caremate_app/lib/state.dart` | 全局状态与动作：拉计划、点确认/稍后、离线队列落盘、联网补传、同步 |
| `caremate_app/pubspec.yaml` | Flutter 依赖：flutter_local_notifications、timezone、shared_preferences、http |

## 文档

| 文件 | 作用 |
|---|---|
| `docs/1_陈秋廷_接口与实现决策清单_已回复.docx` | 课程文档（二进制） |
| `docs/2_手机端_对接契约_v0.1_后端回执.md` | （未标注） |
| `docs/4.2对齐记录_实现与验收.docx` | 课程文档（二进制） |
| `docs/CareMate_学习路径.pdf` | 课程文档（二进制） |
| `docs/Opening_Report_Web_Cloud_修订版.docx` | 课程文档（二进制） |
| `docs/实现步骤对照_11步现状与缺口.docx` | 课程文档（二进制） |
| `docs/开题报告_第2至5节_中文.docx` | 课程文档（二进制） |
| `docs/技术架构_App与Web.docx` | 课程文档（二进制） |
| `docs/设计思路比对_4.2节与当前实现.docx` | 课程文档（二进制） |
| `docs/距离最终目标的学习路径.pdf` | 课程文档（二进制） |

## 验收证据

| 文件 | 作用 |
|---|---|
| `evidence/验收汇总_20261105.md` | （未标注） |

## 根目录

| 文件 | 作用 |
|---|---|
| `.git` | （未标注） |
| `MANIFEST.md` | 本包清单：内容、恢复步骤、已知限制 --> |

