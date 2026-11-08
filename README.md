<!-- 作用：本包说明：定位、状态、上手顺序、已知限制 -->
# v2-qt-core · Qt 路线版的核心代码

`v2-qt` 分支里**真正实现功能**的那部分：Qt/QML 老人端、Android 精确闹钟 JNI、树莓派部署与 MQTT 桥、雷达固件，以及这套线共用的云端服务。

## 核心文件速览

| 功能 | 文件 | 说明 |
|---|---|---|
| 规则→实例（C++ 版） | `app-qt/core/ReminderModel.cpp` | 对照 `server.py` 的 `slots_on()` |
| 老人端界面 | `app-qt/pages/{Today,Record,Family}Page.qml` | 三页 + 底部 tab |
| 呼救 | `app-qt/pages/SosButton.qml` | 按住 3 秒才触发 |
| 精确闹钟 | `app-qt/android/jni/AlarmBridge.cpp` + `app-qt/android/src/com/caremate/app/AlarmBridge.java` | `setExactAndAllowWhileIdle` + 通知渠道 |
| 云端业务 | `legacy-web/server.py` | 与 v1 同一套状态机 |
| MQTT 桥 | `pi/bridge.py` | 零依赖 MQTT 3.1.1：outbox → broker |
| 板子部署 | `pi/mosquitto.conf`、`pi/*.service`、`pi/setup-pi.sh` | 树莓派/香橙派 |
| 雷达固件 | `esp32/esp32_node.ino` | LD2410C + 灯语义表，只上报 |

## 编译 Qt 端

需要 Qt 6.5+ 与 Android Kit：

```bash
cd app-qt
qt-cmake -S . -B build
cmake --build build
```

## 状态（重要）

- `app-qt/`：**骨架，未编译**。搭建工具链时 `download.qt.io` 与镜像返回的 qtbase 包校验失败，所以没验证过编译。
- `pi/`：脚本齐全；`bridge.py` 只做过**报文级**自测（CONNECT/PUBLISH 编码正确），未连真实 broker。
- `esp32/`：源码完整，**未烧录**。
- `legacy-web/`：**已跑通**，七套验收 56/56。

## 与完整分支的关系

完整版在 `v2-qt` 分支；正式交付的客户端是 `main` 分支里的 Flutter 版（`app/`）。

## 分支地图

本分支实际包含：
- `app-qt/`
- `esp32/`
- `legacy-web/`
- `pi/`

不在本分支的常用目录，去哪找：

- `scripts/` —— 系统改造脚本（priv-app / kiosk / 自检）→ `v3-flash`、`v3-flash-core` 或 `main`
- `magisk-module/` —— Magisk 定制层 → `v3-flash`、`v3-flash-core` 或 `main`
- `device/` —— 刷机与回滚 → `v3-flash`、`v3-flash-core` 或 `main`
- `app/` —— Flutter 老人端 → `main` 的 `app/`（本仓库正式交付的客户端）
- `docs/` —— 文档 → `main` 的 `docs/`
