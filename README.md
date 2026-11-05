# v1-web-core · 纯 Web 版的核心代码

`v1-web` 分支里**真正实现功能**的那部分：后端业务、老人端与看板前端、Flutter 端源码、七套验收。文档、证据、数据库、APK 都没有在这里。

## 核心文件速览

| 功能 | 文件 | 关键位置 |
|---|---|---|
| 规则→实例 | `caremate-cloud/server.py` | `slots_on()` / `ensure_occurrences()` |
| **状态迁移（唯一入口）** | `caremate-cloud/server.py` | `transition()` |
| 升级链 2/5/15 | `caremate-cloud/server.py` | `scheduler_tick()` |
| 统计与备份 | `caremate-cloud/server.py` | `stats()` / `do_backup()` |
| 老人端界面 | `caremate-cloud/web/app.html` | 长按呼救、5 秒撤销、语音 |
| 家属看板 | `caremate-cloud/web/dashboard.html` | `watchAlarms()` 长轮询、`incoming()` 弹红条 |
| 手机端动作与离线队列 | `caremate_app/lib/state.dart` | `record()` / `pushPending()` / `sync()` |
| 本地闹钟 | `caremate_app/lib/notify.dart` | `rescheduleAll()` |
| MQTT 桥 | `caremate-cloud/bridge.py` | `pump()` |

## 跑起来

```bash
cd caremate-cloud
python3 server.py --port 8000      # 打开 http://127.0.0.1:8000/dashboard
python3 test_contract.py           # 18 项
```

零第三方依赖（只用 Python 标准库）。

## 状态

后端与看板：**已跑通**，七套验收 56/56。
Flutter 端：源码完整、可 `flutter build apk`，但**未在真机验证过锁屏通知与精确闹钟**。

## 与完整分支的关系

完整版（含文档、部署、证据、APK 说明）在 `v1-web` 分支；主线整合版在 `main`。