# 文件作用（本分支）

> 由各文件头部的「作用：」注释提取；二进制与产物在表中注明。

共 57 个文件。

## APK 与签名说明

| 文件 | 作用 |
|---|---|
| `app/AndroidManifest-补丁.md` | Manifest 补丁说明：加 HOME（默认桌面）与通知策略权限 --> |
| `app/CareMate-release.apk` | 已签名 APK（二进制产物） |
| `app/签名与升级说明.md` | 签名信息、升级规则、演示机注意事项 --> |

## 刷机与回滚

| 文件 | 作用 |
|---|---|
| `device/flash-lineage.sh` | 刷机骨架：校验机型、备份 boot/dtbo/vbmeta、解锁、刷官方 LineageOS |
| `device/rollback.sh` | 回滚：解除 kiosk、禁用 Magisk 模块、按需卸载 App、重启验证 |
| `device/机型对照.md` | 选机标准与 LineageOS 支持机型对照 --> |

## 文档

| 文件 | 作用 |
|---|---|
| `docs/FLASH.md` | 刷机技术方案：8 项改造、3–4 天排期、报告口径 --> |
| `docs/验收清单.md` | 验收清单：后端 / App / 硬件 / 系统改造 --> |

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

## Magisk 定制层

| 文件 | 作用 |
|---|---|
| `magisk-module/customize.sh` | Magisk 安装时执行：检查 APK 是否就位、设置 priv-app 权限 |
| `magisk-module/module.prop` | Magisk 模块元信息（id、名称、版本、描述） |
| `magisk-module/post-fs-data.sh` | 开机早期：修正 priv-app 目录权限（部分 ROM 会校验 SELinux 上下文） |
| `magisk-module/service.sh` | 开机后：Doze 白名单、精确闹钟 appops、免打扰、沉浸式，逐条失败不影响开机 |
| `magisk-module/system/etc/permissions/privapp-permissions-com.caremate.caremate.xml` | 特权应用权限白名单：精确闹钟、通知、免打扰策略、开机、前台服务 --> --> |
| `magisk-module/system/priv-app/CareMate/README.txt` | 说明：把 APK 复制到本目录并命名为 CareMate.apk |

## 系统改造脚本

| 文件 | 作用 |
|---|---|
| `scripts/10-privapp-install.sh` | 把 APK 装成系统特权应用（/system/priv-app）并放权限白名单，免授权拿到精确闹钟 |
| `scripts/20-kiosk-on.sh` | 开启专注模式：设为默认桌面、隐藏状态栏导航栏、屏幕常亮 |
| `scripts/30-kiosk-off.sh` | 一键恢复：还原桌面、状态栏、常亮与自动时间（演示前必须先演这一条） |
| `scripts/40-chaos.sh` | 四种异常一键复现：断网 / 重启 / 改时间 / 连点，用于验收 |
| `scripts/50-verify-system.sh` | 系统改造 8 项自检：priv-app、精确闹钟、通知、Doze、默认桌面、状态栏、进程、AlarmManager |

## 根目录

| 文件 | 作用 |
|---|---|
| `.git` | （未标注） |
| `README.md` | 本包说明：定位、状态、上手顺序、已知限制 --> |

<!-- 文件：FILES.md -->
