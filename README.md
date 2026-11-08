<!-- 作用：本包说明：定位、状态、上手顺序、已知限制 -->
# CareMate · 路线版（B4 Qt + E3-Qt + F1 雷达 + root 安卓）

> 这份包是按《需求扩展与技术路线》里定的**主形态**搭的骨架，不是把原来的网页版改个名。
> 原网页版完整保留在 `legacy-web/`，作为参考实现与回退方案。

## 一、四块东西怎么分工

| 路线编号 | 形态 | 是什么 | 目录 |
|---|---|---|---|
| **B4** | Qt for Android | 老人端 + 家属端**同一个 APK**，QML 两种模式 | `app-qt/` |
| **E3-Qt** | 树莓派 / 香橙派 | 跑 mosquitto broker + 后端 + 桥，同一个设备兼"宠物终端" | `pi/` |
| **F1** | LD2410C 雷达 | ESP32-S3 读雷达 → MQTT；灯光/蜂鸣按语义表反馈 | `esp32/` |
| **—** | root 安卓 14 演示机 | 精确闹钟、白名单、Launcher 替换、chaos 脚本 | `android-root/` |

## 二、当前状态（诚实版）

| 项 | 状态 |
|---|---|
| `legacy-web/` 后端 + 看板 | **已跑通**，七套验收 56/56（见 `docs/验收清单.md`） |
| `pi/` 部署与桥 | 脚本齐全；`bridge.py` 只做过**报文级**自测，未连真 broker |
| `esp32/esp32_node.ino` | 源码完整，**未烧录验证**（无硬件） |
| `app-qt/` | **骨架**：QML 页面、规则模型、JNI 桥的头文件与实现框架都写了，**未编译**（本机无 Qt/NDK） |
| `android-root/` | 脚本齐；命令参照 `dumpsys/am/cmd/settings`，**未在真机执行** |

一句话：**后端与协议是实的，Qt 与硬件是骨架**。报告里按这个口径写，别把骨架说成能用。

## 三、上手顺序（别跳）

1. **先把 `legacy-web/` 跑起来**（`python server.py --port 8000`），确认 `/api/v1/health` 通。
   —— 后端逻辑（rules → occurrence → transition → outbox）已经在里面验证过，Qt 端照着它的行为写，不必重新推演。
2. **树莓派起 broker**：`pi/setup-pi.sh` → `mosquitto_sub -t 'home/#' -v` 能看到消息。
3. **烧 ESP32**：改 WiFi/`MQTT_HOST` → 手在雷达前晃，`mosquitto_sub` 出现 `home/sensor/presence`。
4. **编译 Qt 端**：Qt 6.5+ + Android Kit → `cd app-qt && qt-cmake -S . -B build && cmake --build build`。
5. **演示机 root 脚本**：`android-root/00-precheck.sh` 先看设备到位情况，再逐条执行。

## 四、和文档的对应

- 需求编号 R1–R8 → 落地位置见 `docs/路线对照_R1-R8.md`（每条标了"已有实现 / 本包骨架 / 未做"）。
- topic 与 payload 见 `docs/topics.md`，与报告 4.2.3 完全一致。
- 验收怎么演见 `docs/验收清单.md`。

## 五、这份包**不做**的东西

小程序、AOSP 刷机、自研 ASR/TTS、医疗诊断、真实 120 对接——与文档 §2.9 一致。Qt 端也不做复杂动画与主题系统。

## 六、目录

```
CareMate_路线版_<日期>/
├── README.md                 ← 你在这里
├── app-qt/                   B4：Qt for Android（QML + JNI 桥）
│   ├── CMakeLists.txt
│   ├── main.cpp / main.qml
│   ├── pages/                Today / Record / Family 三页
│   ├── core/                 ReminderModel（规则→实例）
│   └── android/              AndroidManifest + jni/AlarmBridge + build.gradle
├── pi/                       E3-Qt：mosquitto + 服务 + 桥 + 一键安装
├── esp32/                    F1：雷达节点固件
├── android-root/             演示机脚本（精确闹钟/白名单/kiosk/chaos）
├── docs/                     路线对照、topics、验收清单
└── legacy-web/               已跑通的 Python + Web 实现（参考/回退）
```

<!-- 文件：README.md -->

## 分支地图

本分支实际包含：
- `android-root/`
- `app-qt/`
- `docs/`
- `esp32/`
- `legacy-web/`
- `pi/`

不在本分支的常用目录，去哪找：

- `scripts/` —— 系统改造脚本（priv-app / kiosk / 自检）→ `v3-flash`、`v3-flash-core` 或 `main`
- `magisk-module/` —— Magisk 定制层 → `v3-flash`、`v3-flash-core` 或 `main`
- `device/` —— 刷机与回滚 → `v3-flash`、`v3-flash-core` 或 `main`
- `app/` —— Flutter 老人端 → `main` 的 `app/`（本仓库正式交付的客户端）
