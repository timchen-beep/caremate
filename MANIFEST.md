<!-- 作用：本包清单：内容、恢复步骤、已知限制 -->
# CareMate 备份清单

- 备份时间：2026-11-05 16:38
- 后端版本：server.py v1.0.0
- 文件数：58　总大小：1543 KB
- 机器：Windows（开发机）

## 目录

```
CareMate_备份_20261105_1638/
├── caremate-cloud/          后端 + 网页 + 部署 + 固件 + 桥 + 测试
│   ├── server.py            唯一后端（零第三方依赖）
│   ├── bridge.py            MQTT 桥（零依赖，树莓派/香橙派用）
│   ├── web/                 app.html 老人端 / dashboard.html 看板 / kiosk.html 专注模式
│   ├── deploy/              Caddyfile + systemd + setup.sh
│   ├── docs/HARDWARE.md     香橙派 / 树莓派 / ESP32 接入说明
│   ├── firmware/            esp32_node.ino（雷达 + 灯 + 蜂鸣器）
│   ├── test_*.py            六套验收脚本
│   ├── backups/             数据库快照（1 个，最新）
│   ├── README.md / DEMO.md
├── caremate_app/            手机端 Flutter 源码（未编译）
├── evidence/                验收汇总
└── docs/                    报告、对照表、学习路径、契约回执
```

## 没放进备份的（有意排除）

- *.db-wal / *.db-shm：SQLite 运行时文件，恢复用 ackups/ 里的快照。
- step_test.db、	z_test.db 等测试库：随时可由脚本重建。
- __pycache__、uild/、.dart_tool/：编译产物。
- 与本项目无关的课程文档（CASAS 论文、Git 讲义、实验 2 等）。

## 怎么恢复

```bat
:: 1) 解压到任意目录，进后端目录
cd caremate-cloud

:: 2) 用快照覆盖数据库（可选：想要历史数据才需要）
copy backups\caremate-*.db caremate.db

:: 3) 起服务
python server.py --port 8000
:: 验证
curl http://127.0.0.1:8000/api/v1/health
```

首次启动会自动建表并写入演示数据（三个账号、三条计划），不需要手动初始化。

## 恢复后自检（约 3 分钟）

```bat
python test_contract.py   :: 18/18
python test_accept.py     :: 6/6
python test_p2.py         :: 9/9
python test_v06.py        :: 7/7
python test_align.py      :: 9/9
python test_steps.py      :: 7/7
python test_extra.py      :: 7/7（需服务在 8400）
```

## 已知限制（备份里也一样）

1. 老人端是**网页/PWA**，不是 APK：锁屏提醒不可用（要 Flutter 工具链）。
2. Flutter 源码未编译（本机无 SDK），无 ndroid/ 平台目录。
3. 部署脚本未在真实服务器跑过；MQTT 桥未连真 broker 验证（只有报文级自测）。
4. 技术选型与《需求扩展与技术路线》不同：文档要 Qt/MQTT/雷达，本备份是 Python + Web + 预留 MQTT。

<!-- 文件：MANIFEST.md -->
