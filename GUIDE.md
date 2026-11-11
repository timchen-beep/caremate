<!-- 作用：qt 分支的阅读指南：Qt 端的五个落点、改功能改哪里、怎么验证（含没验证的部分） -->
# Qt 老人端怎么读、怎么改

## 1. 从哪读起（按顺序）

| 步骤 | 文件 | 看什么 |
|---|---|---|
| 1 | `qt/pages/TodayPage.qml` | 老人第一眼看到什么、按钮多大 |
| 2 | `qt/core/ReminderModel.cpp` 的 `rebuild()` | 规则怎么变成今天四个提醒 |
| 3 | `qt/core/ReminderModel.cpp` 的 `refresh()` | **端上 30 秒 tick**：到点置 `notified` |
| 4 | `qt/net/SyncPuller.cpp` | 什么时候拉、什么时候推、断网怎么办 |
| 5 | `qt/core/LocalStore.cpp` | 本地主副本落盘（杀进程不丢队列） |

## 2. 改功能改哪里

| 想改什么 | 改这个文件 | 注意 |
|---|---|---|
| 页面文案/布局 | `qt/pages/*.qml` | 老人端字号 ≥24pt、按钮 ≥84px |
| 提醒规则 | `qt/core/ReminderModel.cpp` 的 `matches()` / `dueMinutesFor` | 四种规则（daily/weekly/interval/once） |
| 端上到点行为 | `qt/core/ReminderModel.cpp` 的 `refresh()` | 只置 `notified`；`escalated`/`missed` 由云端 |
| 同步节奏 | `qt/net/SyncPuller.cpp` 的 `m_timer` | 默认 15 秒 |
| 接口地址/令牌 | `qt/net/HttpClient.cpp` 的构造函数 | `CAREMATE_API` / `CAREMATE_TOKEN` |
| 状态机 | 后端 `server/server.py` 的 `transition()` | 端上不自己判终态 |

## 3. 验证

```bash
# 后端（本分支可跑）
cd server && python3 server.py --port 8400 &
python3 test_v1.py            # 9 项：形状/游标/事件/去重/409/配对/告警/ID 公式

# 全量（21 项，含九套后端验收）
python tools/verify_all.py
```

Qt 端本身：**本机没有 Qt kit，未编译**。在装了 Qt 6.5+ 的机器上：

```bash
cd qt && cmake -S . -B build && cmake --build build -j6 && ./build/appCareMate
```

## 4. 三个容易踩的坑

1. `SyncPuller` 一次只跑一个请求（回执按 `m_pendingOp` 分派），别改成并发——会把事件回执错配。
2. `applyRemoteOccurrences()` 会用服务端状态**覆盖**本地；端上 tick 改的 `notified` 会在下一轮被云端覆盖，这是设计（云端权威）。
3. 新增 `.qml` 要同时加进 `qt/CMakeLists.txt` 的 `QML_FILES`，否则运行时找不到资源——`verify_all` 的"构建引用一致"守卫会拦。