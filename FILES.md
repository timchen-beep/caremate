# 代码地图

<!-- 作用：文件索引：每个文件一行说明，由各文件头部的注释自动生成 -->

> 由各文件头部的 `作用：` 注释自动提取；改代码时改注释，重跑生成脚本即可。

共 137 个文件。

| 目录 | 文件数 | 说明 |
|---|---|---|
| `server` | 31 | 后端与页面 |
| `.github` | 2 | CI |
| `app` | 39 | Flutter 老人端 |
| `device` | 4 | 刷机与回滚 |
| `docs` | 13 | 文档 |
| `magisk-module` | 7 | Magisk 定制层 |
| `pi` | 6 | 树莓派 / 香橙派部署 |
| `qt` | 15 | Qt/QML 老人端骨架 |
| `scripts` | 6 | 系统改造脚本 |
| `tools` | 4 | 辅助工具 |
| `（根目录）` | 10 | 仓库根 |

## 后端与页面（31）

| 文件 | 作用 |
|---|---|
| `server/DEMO.md` | 8 分钟演示脚本（后端侧）：怎么起服务、怎么演到点与呼救 |
| `server/README.md` | 后端说明：接口清单、部署方式、验收命令与设计取舍 |
| `server/bridge.py` | MQTT 桥：把 outbox 里的事件用零依赖 MQTT 3.1.1 客户端 publish 到 broker，再标记已消费 |
| `server/deploy/Caddyfile` | 反向代理与自动 HTTPS：把域名转发到 127.0.0.1:8000 |
| `server/deploy/README.md` | 部署说明：反代终止 TLS、应用单进程的原因与步骤 |
| `server/deploy/caremate.service` | systemd 单元：以单进程跑后端（多进程会有两个调度循环） |
| `server/deploy/setup.sh` | 服务器一键部署：装 Python/tzdata、建 systemd 单元、起服务并用 curl 自检 |
| `server/docs/HARDWARE.md` | 硬件接入：香橙派/树莓派/ESP32 分工、接线、topic 表 |
| `server/evidence-验收汇总.md` | 七套验收的汇总证据：命令、时间、通过数（由 tools/collect_evidence.py 生成） |
| `server/firmware/esp32_node.ino` | ESP32 传感器节点：读 LD2410C 雷达并上报 presence，收告警按语义表点灯/蜂鸣（不含业务判断） |
| `server/server.py` | CareMate 云端唯一服务：规则展开、实例物化、状态迁移、升级链调度、统计、备份、页面路由（零第三方依赖） |
| `server/start.bat` | Windows 本地启动器：ASCII 输出，避免中文代码页乱码 |
| `server/test_accept.py` | 可靠性验收 6 项：P95 派发、断网补传、越权 403、升级链自驱、10 次重启不丢不重 |
| `server/test_align.py` | 一致性 9 项：from/to 反序 400、改计划历史不变、换时区不新增行、单入口检查 |
| `server/test_auto_scheduler.py` | 调度器手动验证脚本：不碰页面也能自己升级（开发用） |
| `server/test_contract.py` | 契约验收 18 项：鉴权、from/to、事件提交幂等、数组/信封、错误码 |
| `server/test_extra.py` | 新增能力 7 项：七天预览、传感器事件、通知通道、专注模式、--demo/--preview |
| `server/test_p2.py` | 令牌与权限 9 项：配对换令牌、越权访问、一次性规则、角色边界 |
| `server/test_steps.py` | 交互 7 项：呼救、5 秒撤销、记录撤销留痕、久未活动、专注模式页 |
| `server/test_sync.py` | 端云同步验收 5 项：批量上行、幂等去重、越权拒绝、回灌游标、端侧告警 |
| `server/test_v06.py` | 工程性 7 项：派发延迟、限流 429、磁盘水位 507、备份、单实例保护 |
| `server/web/README.md` | 服务端页面的说明：三个页面各给谁用、各自的关键函数 |
| `server/web/app.html` | 老人端网页/PWA：大字高对比、语音播报、长按呼救、确认/稍后、记录与自检 |
| `server/web/apple-touch-icon.png` | iOS 主屏图标 |
| `server/web/dashboard.html` | 家属看板：5 秒刷新今日进度、长轮询收告警弹红条、计划/记录/告警/统计/云端五个分区 |
| `server/web/icon-192.png` | PWA 图标 192×192 |
| `server/web/icon-512.png` | PWA 图标 512×512 |
| `server/web/index.html` | 落地页：项目介绍与三个入口（/app、/dashboard、/kiosk） |
| `server/web/kiosk.html` | 专注模式页面：四个大按钮，长按左上角 5 秒退出 |
| `server/web/manifest.webmanifest` | PWA 清单：应用名、图标、显示方式（JSON 不支持注释） |
| `server/web/sw.js` | Service Worker：缓存静态页，让老人端可离线打开 |

## CI（2）

| 文件 | 作用 |
|---|---|
| `.github/workflows/ci.yml` | CI：push/PR 时在 Ubuntu 上跑 tools/verify_all.py（语法 + 七套验收 + 页面检查 + 完整性守卫） |
| `.github/workflows/flutter-build.yml` | 手动触发的 APK 构建（release/debug 可选，产物上传为 artifact） |

## Flutter 老人端（39）

| 文件 | 作用 |
|---|---|
| `app/.gitignore` | Flutter 默认忽略规则（构建产物、工具链临时文件） |
| `app/.metadata` | Flutter 项目元数据：版本与迁移信息，不要手改 |
| `app/README.md` | 老人端 App 说明：老人端/看护端形态分工、权限、构建与安装步骤 |
| `app/analysis_options.yaml` | Dart 静态检查规则（flutter_lints） |
| `app/android/.gitignore` | Android 模块忽略规则（本地 SDK 路径、构建缓存） |
| `app/android/app/build.gradle` | 应用模块构建：namespace、targetSdk、release 签名（无 key.properties 时退回 debug 签名） |
| `app/android/app/src/debug/AndroidManifest.xml` | 调试清单（Flutter 生成）：允许明文 HTTP，便于本地联调 |
| `app/android/app/src/main/AndroidManifest.xml` | 老人端清单：通知、精确闹钟、开机重排、振动与唤醒锁 |
| `app/android/app/src/main/kotlin/com/caremate/caremate/MainActivity.kt` | Android 宿主 Activity，只负责把 Flutter 引擎挂起来（无业务逻辑） |
| `app/android/app/src/main/res/drawable-v21/launch_background.xml` | 启动画面背景的 API 21+ 变体（Flutter 生成） |
| `app/android/app/src/main/res/drawable/launch_background.xml` | 启动画面背景（Flutter 生成） |
| `app/android/app/src/main/res/mipmap-hdpi/ic_launcher.png` | 应用图标 hdpi |
| `app/android/app/src/main/res/mipmap-mdpi/ic_launcher.png` | 应用图标 mdpi |
| `app/android/app/src/main/res/mipmap-xhdpi/ic_launcher.png` | 应用图标 xhdpi |
| `app/android/app/src/main/res/mipmap-xxhdpi/ic_launcher.png` | 应用图标 xxhdpi |
| `app/android/app/src/main/res/mipmap-xxxhdpi/ic_launcher.png` | 应用图标 xxxhdpi |
| `app/android/app/src/main/res/values-night/styles.xml` | 夜间主题样式（Flutter 生成） |
| `app/android/app/src/main/res/values/styles.xml` | 日间主题样式（Flutter 生成） |
| `app/android/app/src/profile/AndroidManifest.xml` | 性能分析清单（Flutter 生成）：申请网络权限 |
| `app/android/build.gradle` | Android 构建根配置：AGP 与 Kotlin 插件版本、仓库 |
| `app/android/gradle.properties` | Gradle 运行参数：JVM 内存、AndroidX 开关 |
| `app/android/gradle/wrapper/gradle-wrapper.jar` | Gradle wrapper 可执行 jar（缺了无法构建） |
| `app/android/gradle/wrapper/gradle-wrapper.properties` | Gradle 版本与分发地址（CI 里换回官方源） |
| `app/android/gradlew` | Gradle wrapper（Unix 脚本），构建入口之一 |
| `app/android/gradlew.bat` | Gradle wrapper（Windows 脚本），构建入口之一 |
| `app/android/settings.gradle` | Gradle 设置：加载 Flutter 插件、声明依赖仓库（FAIL_ON_PROJECT_REPOS） |
| `app/lib/README.md` | Flutter 端源码的说明：文件分工与数据流 |
| `app/lib/api.dart` | HTTP 客户端：Bearer 令牌、JSON 编解码、错误码到中文提示的映射 |
| `app/lib/device_scheduler.dart` | 端上 30 秒 tick（4.1 架构图第 3 层）：到点把本地实例置 notified 并触发本机通知；升级与告警仍由云端兜底 |
| `app/lib/local_db.dart` | 手机端本地库（4.1 架构图第 3 层）：plans / occurrences / events 三表 + 同步游标，冷启动先读这里 |
| `app/lib/main.dart` | App 入口：初始化状态与本地通知，挂三个 tab（今天/记录/我的） |
| `app/lib/models.dart` | 数据模型：Occurrence / Plan / AppEvent，字段与契约 v0.1 一一对应 |
| `app/lib/notify.dart` | 本地通知：通知渠道、按计划重排精确闹钟（setExactAndAllowWhileIdle）、开机重排 |
| `app/lib/screens/records.dart` | 记录页：今日统计、今天要做的事、已提交动作（含未同步标记） |
| `app/lib/screens/settings.dart` | 我的页：服务器地址与令牌、配对码、通知自检、同步状态 |
| `app/lib/screens/today.dart` | 今天页：到点卡片 + 吃了/等会儿/没做 三个大按钮 |
| `app/lib/state.dart` | 全局状态与动作：拉计划、点确认/稍后、离线队列落盘、联网补传、同步 |
| `app/pubspec.lock` | 依赖版本锁定文件，保证不同机器装到同一批依赖 |
| `app/pubspec.yaml` | Flutter 依赖：本地库（sqflite）、本地通知、精确闹钟、离线设置 |

## 刷机与回滚（4）

| 文件 | 作用 |
|---|---|
| `device/README.md` | 刷机方向的说明：选什么机型、怎么刷、怎么回滚、风险在哪 |
| `device/flash-lineage.sh` | 刷机骨架：校验机型、备份 boot/dtbo/vbmeta、解锁、刷官方 LineageOS |
| `device/rollback.sh` | 回滚：解除 kiosk、禁用 Magisk 模块、按需卸载 App、重启验证 |
| `device/机型对照.md` | 选机标准与 LineageOS 官方支持机型对照，含小米解锁等 7 天时延提示 |

## 文档（13）

| 文件 | 作用 |
|---|---|
| `docs/Opening_Report_Web_Cloud_修订版_v3.docx` | 报告 4.2 正文（v3）：接口前缀/两族、双时间字段、P95 实测、调度器端上为主 |
| `docs/README.md` | 文档目录的说明：每份文档解决什么问题、什么时候看 |
| `docs/topics.md` | MQTT topic 与 payload 约定，含发布方/订阅方与频率说明 |
| `docs/云部署.md` | 上云部署步骤：买机、换令牌、systemd、Caddy、验证、备份（约 40 分钟） |
| `docs/契约_手机端对接_v0.1.md` | 手机端与后端的接口契约回执：七条接口逐条确认与差异说明 |
| `docs/按4.1架构改造计划.md` | 按 4.1 架构图（端上主副本 + 端上调度）改造的实施计划：目标、与现状的 5 处差异、分步清单、已踩的坑 |
| `docs/接口与指标口径.md` | 接口与指标口径：前缀、两族划分、event_id 归属、时间双字段、格式约定、P95 口径与复现 |
| `docs/演示脚本.md` | 8 分钟演示脚本：六段流程，换个人照纸条也能演完 |
| `docs/硬件接入.md` | 硬件接入：香橙派/树莓派/ESP32 分工、接线、topic 表、没网怎么演示 |
| `docs/端云同步接口.md` | 端云同步接口说明：三条接口的语义、请求/响应示例、与 4.1 架构图第 5 层的对应 |
| `docs/评审答复_4.2.md` | 对 4.2 评审意见的答复：三条报告修改的结论、四个接口问题的取舍、方案 B 的实施与实测 |
| `docs/路线对照_R1-R8.md` | 需求编号 R1–R8 → 落地位置与状态（已有实现/骨架/未做） |
| `docs/验收清单.md` | 验收清单：后端七套、App 真机、硬件、系统改造四类检查项 |

## Magisk 定制层（7）

| 文件 | 作用 |
|---|---|
| `magisk-module/README.md` | Magisk 定制层的说明：模块结构、安装方式、为什么能一键回滚 |
| `magisk-module/customize.sh` | Magisk 安装时执行：检查 APK 是否就位、设置 priv-app 权限 |
| `magisk-module/module.prop` | Magisk 模块元信息（id、名称、版本、描述） |
| `magisk-module/post-fs-data.sh` | 开机早期：修正 priv-app 目录权限（部分 ROM 会校验 SELinux 上下文） |
| `magisk-module/service.sh` | 开机后：Doze 白名单、精确闹钟 appops、免打扰、沉浸式，逐条失败不影响开机 |
| `magisk-module/system/etc/permissions/privapp-permissions-com.caremate.caremate.xml` | 特权应用权限白名单：精确闹钟、通知、免打扰策略、开机、前台服务 |
| `magisk-module/system/priv-app/CareMate/README.txt` | 说明：把 app/CareMate-release.apk 复制到本目录并命名为 CareMate.apk |

## 树莓派 / 香橙派部署（6）

| 文件 | 作用 |
|---|---|
| `pi/README.md` | 树莓派/香橙派部署说明：装什么、怎么起、怎么自检 |
| `pi/bridge.py` | 树莓派/香橙派上的 MQTT 桥（与 server/bridge.py 同一实现，按板子部署习惯放置） |
| `pi/caremate-bridge.service` | 树莓派 systemd 单元：跑 MQTT 桥（outbox → broker） |
| `pi/caremate-server.service` | 树莓派 systemd 单元：板子上以单进程跑后端 |
| `pi/mosquitto.conf` | mosquitto 配置：监听 1883、持久化、日志位置 |
| `pi/setup-pi.sh` | 板子一键安装：apt 装 mosquitto、放 broker 配置、装两个 systemd、起服务并自检 |

## Qt/QML 老人端骨架（15）

| 文件 | 作用 |
|---|---|
| `qt/CMakeLists.txt` | Qt 工程构建：QML 模块声明、Android 包源码目录 |
| `qt/README.md` | Qt 骨架说明：为什么保留、目录结构、怎么编译、哪些还没验证 |
| `qt/android/AndroidManifest.xml` | Qt 端清单：精确闹钟、通知、开机重排、前台服务权限 |
| `qt/android/build.gradle` | Qt for Android 的 Gradle 配置（AGP 8.1、compileSdk 34） |
| `qt/android/jni/AlarmBridge.cpp` | 用 QJniObject 调 Java 侧的闹钟与通知渠道，桌面构建时打印模拟 |
| `qt/android/jni/AlarmBridge.h` | Android 精确闹钟桥的 C++ 接口（schedule/cancel/canScheduleExactAlarms） |
| `qt/android/src/com/caremate/app/AlarmBridge.java` | Java 侧：AlarmManager.setExactAndAllowWhileIdle + 通知渠道（普通/呼救两级） |
| `qt/core/ReminderModel.cpp` | Qt 规则模型的实现：七种规则展开、30 秒刷新到期判断（对照后端 slots_on/transition） |
| `qt/core/ReminderModel.h` | Qt 规则模型的接口：规则→实例、确认/稍后/未做、到期列表 |
| `qt/main.cpp` | Qt 入口：注册 ReminderModel、加载 main.qml（Android 走 Qt for Android） |
| `qt/main.qml` | Qt 外壳：三 tab 布局、字号/按钮尺寸常量（32px 正文、84px 按钮） |
| `qt/pages/FamilyPage.qml` | Qt 家属模式：今日实例列表 + 代确认（同一 APK 的另一种界面） |
| `qt/pages/RecordPage.qml` | Qt 记录页：喝水/入睡/起床一键记录 |
| `qt/pages/SosButton.qml` | Qt 呼救按钮：按住 3 秒才触发，松手取消 |
| `qt/pages/TodayPage.qml` | Qt 今天页：到点卡片 + 三个 84 高的大按钮 |

## 系统改造脚本（6）

| 文件 | 作用 |
|---|---|
| `scripts/10-privapp-install.sh` | 把 APK 装成系统特权应用（/system/priv-app）并放权限白名单，免授权拿到精确闹钟 |
| `scripts/20-kiosk-on.sh` | 开启专注模式：设为默认桌面、隐藏状态栏导航栏、屏幕常亮 |
| `scripts/30-kiosk-off.sh` | 一键恢复：还原桌面、状态栏、常亮与自动时间（演示前必须先演这一条） |
| `scripts/40-chaos.sh` | 四种异常一键复现：断网 / 重启 / 改时间 / 连点，用于验收 |
| `scripts/50-verify-system.sh` | 系统改造 8 项自检：priv-app、精确闹钟、通知、Doze、默认桌面、状态栏、进程、AlarmManager |
| `scripts/README.md` | Android 系统级改造脚本的说明：每个脚本做什么、按什么顺序执行、怎么回滚 |

## 辅助工具（4）

| 文件 | 作用 |
|---|---|
| `tools/README.md` | 辅助工具的说明：怎么跑七套验收并生成一份证据文件 |
| `tools/collect_evidence.py` | 跑七套验收并把结果汇总成一份 markdown 证据文件 |
| `tools/sample_p95.py` | 一键取 P95 真实样本：干净端口 + 临时库 → 建 40 秒后的计划 → 等调度器派发 → 打印派发延迟 |
| `tools/verify_all.py` | 一键全量验证：完整性守卫 + 语法检查 + 七套验收 + 四个页面 HTTP 检查（可选 flutter analyze） |

## 仓库根（10）

| 文件 | 作用 |
|---|---|
| `.gitattributes` | 行尾规则：仓库存 LF、bat 用 CRLF、二进制文件不做转换 |
| `.gitignore` | 忽略规则：数据库、签名私钥、构建产物、APK、CI 临时文件 |
| `CONTRIBUTING.md` | 开发规约：改代码的三条铁律、一键验证怎么跑、提交与分支规范、踩过的坑 |
| `FILES.md` | 文件索引：每个文件一行说明（由各文件头部注释生成） |
| `FUNCTIONS.md` | 函数索引：每个函数一行说明（由代码注释生成） |
| `GUIDE.md` | 给第一次看这个仓库的人：项目是什么、代码怎么跑、从哪读起、改功能改哪里 |
| `LICENSE` | MIT 许可证（内容为标准文本，未加注释） |
| `PUSH.md` | 推送到 GitHub 的 3 条命令、常见报错与仓库内容边界 |
| `README.md` | 项目总览：架构图、目录、每条分支里有什么、两份索引入口、快速开始、验收命令、设计取舍、已知限制 |
| `push-all.bat` | 一次推送 main 与三条归档分支（本地辅助脚本） |

