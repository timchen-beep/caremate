# 文件作用（本分支）

> 由各文件头部的「作用：」注释提取；二进制与产物在表中注明。

共 66 个文件。

## 演示机 root 脚本

| 文件 | 作用 |
|---|---|
| `android-root/00-precheck.sh` | 预检：确认演示机是否已 root、包是否已装、精确闹钟权限状态 |
| `android-root/10-grant-exact-alarm.sh` | 授予精确闹钟权限 + Doze 白名单 + 通知权限（root 机器免手动设置） |
| `android-root/30-kiosk.sh` | 把手机锁成只有这一个 App（含 off 恢复分支） |
| `android-root/40-chaos.sh` | 四种异常复现：断网 / 重启 / 改时间 / 连点 |

## Qt/QML 老人端

| 文件 | 作用 |
|---|---|
| `app-qt/CMakeLists.txt` | Qt 工程构建：QML 模块声明、Android 包源码目录 |
| `app-qt/android/AndroidManifest.xml` | Qt 端清单：精确闹钟、通知、开机重排、前台服务权限 --> --> |
| `app-qt/android/build.gradle` | Qt for Android 的 Gradle 配置（AGP 8.1、compileSdk 34） |
| `app-qt/android/jni/AlarmBridge.cpp` | 用 QJniObject 调 Java 侧的闹钟与通知渠道，桌面构建时打印模拟 |
| `app-qt/android/jni/AlarmBridge.h` | Android 精确闹钟桥的 C++ 接口（schedule/cancel/canScheduleExactAlarms） |
| `app-qt/android/src/com/caremate/app/AlarmBridge.java` | Java 侧：AlarmManager.setExactAndAllowWhileIdle + 通知渠道（普通/呼救两级） |
| `app-qt/core/ReminderModel.cpp` | Qt 规则模型的实现：七种规则展开、30 秒刷新到期判断（对照后端 slots_on/transition） |
| `app-qt/core/ReminderModel.h` | Qt 规则模型的接口：规则→实例、确认/稍后/未做、到期列表 |
| `app-qt/main.cpp` | Qt 入口：注册 ReminderModel、加载 main.qml（Android 走 Qt for Android） |
| `app-qt/main.qml` | Qt 外壳：三 tab 布局、字号/按钮尺寸常量（32px 正文、84px 按钮） |
| `app-qt/pages/FamilyPage.qml` | Qt 家属模式：今日实例列表 + 代确认（同一 APK 的另一种界面） |
| `app-qt/pages/RecordPage.qml` | Qt 记录页：喝水/入睡/起床一键记录 |
| `app-qt/pages/SosButton.qml` | Qt 呼救按钮：按住 3 秒才触发，松手取消 |
| `app-qt/pages/TodayPage.qml` | Qt 今天页：到点卡片 + 三个 84 高的大按钮 |

## 文档

| 文件 | 作用 |
|---|---|
| `docs/topics.md` | MQTT topic 与 payload 约定 --> |
| `docs/路线对照_R1-R8.md` | 需求编号 R1–R8 → 落地位置与状态 --> |
| `docs/验收清单.md` | 验收清单：后端 / App / 硬件 / 系统改造 --> |

## 雷达固件

| 文件 | 作用 |
|---|---|
| `esp32/esp32_node.ino` | ESP32 传感器节点：读 LD2410C 雷达并上报 presence，收告警按语义表点灯/蜂鸣（不含业务判断） |

## 后端与页面（本线共用）

| 文件 | 作用 |
|---|---|
| `legacy-web/DEMO.md` | 8 分钟演示脚本（六段流程：开机→到点→确认→家属端→呼救→异常） --> |
| `legacy-web/README.md` | 后端说明：接口、部署、验收 --> |
| `legacy-web/acceptance.json` | 验收报告（测试自动生成，产物） |
| `legacy-web/acceptance_align.json` | 验收报告（测试自动生成，产物） |
| `legacy-web/acceptance_contract.json` | 验收报告（测试自动生成，产物） |
| `legacy-web/acceptance_extra.json` | 验收报告（测试自动生成，产物） |
| `legacy-web/acceptance_p2.json` | 验收报告（测试自动生成，产物） |
| `legacy-web/acceptance_steps.json` | 验收报告（测试自动生成，产物） |
| `legacy-web/acceptance_v06.json` | 验收报告（测试自动生成，产物） |
| `legacy-web/bridge.py` | MQTT 桥：把 outbox 里的事件用零依赖 MQTT 3.1.1 客户端 publish 到 broker，再标记已消费 |
| `legacy-web/deploy/Caddyfile` | 反向代理与自动 HTTPS：把域名转发到 127.0.0.1:8000 |
| `legacy-web/deploy/README.md` | 部署说明：Caddy + systemd 的单机方案 --> |
| `legacy-web/deploy/caremate.service` | systemd 单元：以单进程跑后端（多进程会有两个调度循环） |
| `legacy-web/deploy/setup.sh` | 服务器一键部署：装 Python/tzdata、建 systemd 单元、起服务并用 curl 自检 |
| `legacy-web/docs/HARDWARE.md` | 硬件接入：香橙派/树莓派/ESP32 分工、接线、topic 表 |
| `legacy-web/evidence-验收汇总.md` | 七套验收的汇总证据（由 tools/collect_evidence.py 生成） --> --> |
| `legacy-web/firmware/esp32_node.ino` | ESP32 传感器节点：读 LD2410C 雷达并上报 presence，收告警按语义表点灯/蜂鸣（不含业务判断） |
| `legacy-web/server.py` | CareMate 云端唯一服务：规则展开、实例物化、状态迁移、升级链调度、统计、备份、页面路由（零第三方依赖） |
| `legacy-web/start.bat` | Windows 本地启动器：ASCII 输出，避免中文代码页乱码 |
| `legacy-web/test_accept.py` | 可靠性验收 6 项：P95 派发、断网补传、越权 403、升级链自驱、10 次重启不丢不重 |
| `legacy-web/test_align.py` | 一致性 9 项：from/to 反序 400、改计划历史不变、换时区不新增行、单入口检查 |
| `legacy-web/test_auto_scheduler.py` | 调度器手动验证脚本：不碰页面也能自己升级（开发用） |
| `legacy-web/test_contract.py` | 契约验收 18 项：鉴权、from/to、事件提交幂等、数组/信封、错误码 |
| `legacy-web/test_extra.py` | 新增能力 7 项：七天预览、传感器事件、通知通道、专注模式、--demo/--preview |
| `legacy-web/test_p2.py` | 令牌与权限 9 项：配对换令牌、越权访问、一次性规则、角色边界 |
| `legacy-web/test_steps.py` | 交互 7 项：呼救、5 秒撤销、记录撤销留痕、久未活动、专注模式页 |
| `legacy-web/test_v06.py` | 工程性 7 项：派发延迟、限流 429、磁盘水位 507、备份、单实例保护 |
| `legacy-web/web/app.html` | 老人端网页/PWA：大字高对比、语音播报、长按呼救、确认/稍后、记录与自检 --> --> |
| `legacy-web/web/apple-touch-icon.png` | 图片资源 |
| `legacy-web/web/dashboard.html` | 家属看板：5 秒刷新今日进度、长轮询收告警弹红条、计划/记录/告警/统计/云端五个分区 --> --> |
| `legacy-web/web/icon-192.png` | 图片资源 |
| `legacy-web/web/icon-512.png` | 图片资源 |
| `legacy-web/web/index.html` | 落地页：介绍与入口（/app、/dashboard、/kiosk） --> --> |
| `legacy-web/web/kiosk.html` | 专注模式页面：四个大按钮，长按左上角 5 秒退出 --> --> |
| `legacy-web/web/manifest.webmanifest` | PWA 清单：名称、图标、显示方式 |
| `legacy-web/web/sw.js` | Service Worker：缓存静态页，让老人端可离线打开 |

## 树莓派 / 香橙派部署

| 文件 | 作用 |
|---|---|
| `pi/bridge.py` | 树莓派/香橙派上的 MQTT 桥（与 server/bridge.py 同一实现，按板子部署习惯放置） |
| `pi/caremate-bridge.service` | 树莓派 systemd 单元：跑 MQTT 桥（outbox → broker） |
| `pi/caremate-server.service` | 树莓派 systemd 单元：板子上以单进程跑后端 |
| `pi/mosquitto.conf` | mosquitto 配置：监听 1883、持久化、日志位置 |
| `pi/setup-pi.sh` | 板子一键安装：apt 装 mosquitto、放 broker 配置、装两个 systemd、起服务并自检 |

## 根目录

| 文件 | 作用 |
|---|---|
| `.git` | （未标注） |
| `MANIFEST.md` | 本包清单：内容、恢复步骤、已知限制 --> |
| `README.md` | 本包说明：定位、状态、上手顺序、已知限制 --> |

<!-- 文件：FILES.md -->
