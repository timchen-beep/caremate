# CareMate · 独居老人生活助手

> 老人端 App + 家属 Web 看板 + 一个云端服务。提醒到点必响，未确认会升级，家属随时可看。

本仓库是课程项目 **CareMate** 的完整源码：可运行的后端与看板、可安装的 Flutter 老人端、硬件接入与系统级 kiosk 的可执行脚本。

## 它解决什么

独居老人最常见的两个问题：**忘了吃药** 和 **没人知道他忘没忘**。所以系统做三件事：

1. **提醒在手机上独立成立**：本地闹钟 + 锁屏通知，断网、飞行模式照响（不依赖服务器）
2. **未确认会升级**：2 分钟本机提醒 → 5 分钟通知家属 → 15 分钟记"未确认"，由云端调度器驱动，**不依赖任何页面打开**
3. **家属能看到**：Web 看板实时显示完成情况、告警，呼救 1 秒内弹红条

## 架构

```
[老人手机 Flutter APK]                 [家属 Web 看板]
  本地闹钟 / 本地通知                   浏览器即可，无需安装
  离线动作队列                  ▲
        │ HTTPS（JSON，契约 v0.1）│ 长轮询（告警 <1s 到达）
        ▼                        │
  ┌──────────────────────────────┴─────────┐
  │ 云端：Python 3 标准库 + SQLite（零依赖） │
  │ plan → occurrence → event → outbox     │
  │ transition() 唯一改状态；30s 调度器     │
  └──────────────────┬─────────────────────┘
                     │ MQTT（可选）
              [树莓派 broker + ESP32 雷达]
```

## 目录

| 目录 | 内容 |
|---|---|
| `server/` | Python 后端、老人端网页预览、家属看板、部署脚本、MQTT 桥、ESP32 固件、七套验收脚本 |
| `app/` | **Flutter 老人端（正式交付）**，已能 `flutter build apk` |
| `qt/` | Qt/QML 老人端（B4 路线，骨架，未编译）——契约相同，可平替 `app/` |
| `pi/` | 树莓派/香橙派部署：mosquitto 配置、systemd、零依赖 MQTT 桥 |
| `docs/` | 手机端契约、演示脚本、硬件接入、云部署、R1–R8 需求对照、验收清单 |
| `scripts/` | 系统改造脚本：priv-app 安装、kiosk 开关、chaos 复现、8 项自检 |
| `device/` | 刷机方向：选机对照、刷 LineageOS、回滚 |
| `magisk-module/` | 可整体禁用的 kiosk 定制层 |

## 快速开始（3 条命令）

```bash
cd server
python3 server.py --port 8000
# 浏览器打开 http://127.0.0.1:8000/dashboard
```

默认账号（**仅本地演示**，上公网前必须改）：

| 角色 | 令牌 |
|---|---|
| 老人 | `app-elder-001` |
| 家属 | `fam-demo-2026` |
| 社区 | `comm-demo-2026` |

配对码 `8823`。老人端网页预览：`/app`；专注模式：`/kiosk`。

## 验收

```bash
cd server
python test_contract.py   # 契约 18 项
python test_accept.py     # 可靠性 6 项（含 10 次重启、p95、幂等）
python test_p2.py         # 令牌/权限/一次性规则 9 项
python test_v06.py        # 派发延迟/限速/磁盘水位/备份 7 项
python test_align.py      # 时区/历史不变/单入口 9 项
python test_steps.py      # 呼救/撤销/无动静 7 项
```

全部通过时输出 `总计：X/X 通过`。

## 老人端 App

```bash
cd app
flutter pub get
flutter build apk --release     # 需要 Android SDK 与 JDK 17
```

产物：`build/app/outputs/flutter-apk/app-release.apk`。
Release 签名需要 `android/key.properties` + keystore（仓库里不放私钥，参考 `docs/`）。

> 已知限制：APK 未在真机验证；Android 14 需手动开启「精确闹钟」权限。

## 设计取舍（答辩会被问）

| 取舍 | 理由 |
|---|---|
| 客户端 Flutter，不转 Qt | Flutter 已验证能出签名包；契约与数据模型独立于客户端，将来可平替 |
| 状态只在服务端 | 这是"提醒不丢不重"能成立的前提 |
| 云端单进程 | 两个 worker 会有两个调度循环，提醒发两遍 |
| 不做电话/短信 | 需要运营商资质与费用；通道预留 Webhook |
| 不做医疗判断 | 只提示"请联系家属/医生"，不给补服建议 |

## 已知限制

1. 老人端 APK 已编译签名，**未在真机安装验证**（锁屏通知、精确闹钟仍待实测）。
2. MQTT 桥与 ESP32 固件已写，**未连真实 broker / 未烧录**。
3. 刷机与系统改造脚本**未在真机执行**。
4. 部署脚本未在真实服务器跑过。

## License

MIT