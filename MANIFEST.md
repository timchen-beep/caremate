<!-- 作用：本包清单：内容、恢复步骤、已知限制 -->
# CareMate 路线版 · 备份清单

- 打包时间：2026-11-05 16:41
- 依据：《需求扩展与技术路线》（B4 Qt + E3-Qt 树莓派 + F1 雷达 + root 安卓）
- 文件数：64　大小：358 KB
- 后端版本：v1.0.0（legacy-web/server.py）

## 状态一句话

**后端与协议是实的（56/56 验收通过），Qt 端与硬件是骨架（未编译、未烧录）。**
报告里必须按这个口径写，别把骨架说成能用。

## 各部分完成度

| 目录 | 是什么 | 完成度 |
|---|---|---|
| legacy-web/ | Python 后端 + 老人端网页 + 家属看板 + 七套测试 | 可用（已验收） |
| pp-qt/ | B4 老人端/家属端 QML + JNI 闹钟桥 | 骨架，未编译 |
| pi/ | mosquitto 配置 + systemd + bridge.py + 一键脚本 | 脚本齐；桥未连真 broker |
| esp32/ | LD2410C 雷达节点固件 | 源码完整，未烧录 |
| ndroid-root/ | 精确闹钟/白名单/kiosk/chaos 脚本 | 脚本齐，未在真机执行 |
| docs/ | R1–R8 对照、topic 表、验收清单 | 已写 |

## 怎么用（先跑起来再谈硬件）

```bat
:: 1) 先确认后端没问题
cd legacy-web
python server.py --port 8000
curl http://127.0.0.1:8000/api/v1/health
python test_accept.py

:: 2) 板子（树莓派/香橙派）
bash pi/setup-pi.sh
mosquitto_sub -h 127.0.0.1 -t 'home/#' -v

:: 3) ESP32：改 WiFi 与 MQTT_HOST 后烧 esp32/esp32_node.ino

:: 4) Qt 端
cd app-qt && qt-cmake -S . -B build && cmake --build build

:: 5) 演示机
bash android-root/00-precheck.sh
```

## 没放进来的

- 数据库运行文件（*.db-wal/shm）与测试库；legacy-web 首次启动会自动建库并写入演示数据。
- 与本项目无关的课程文档。

## 已知限制（4 条）

1. Qt 端未编译：本机没有 Qt 6.5 + Android NDK/Kit。JNI 那层要用真机验证，桌面版只能验证 QML 布局。
2. 桥未连真 broker：ridge.py 只做过报文级自测（CONNECT/PUBLISH 编码正确）。
3. ESP32 未烧录：没有硬件；接线与 topic 见 docs/HARDWARE.md（在 legacy-web/docs/）。
4. root 脚本未执行：命令依照 dumpsys/am/cmd/settings 官方用法写，但没在真机跑过；30-kiosk.sh 一定先演 off 再演 on。