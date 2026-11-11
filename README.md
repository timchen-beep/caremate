<!-- 作用：qt 分支说明：只做 Qt/QML 老人端路线（客户端骨架 + 后端 + 对接补丁），迭代都在这里 -->
# CareMate · Qt/QML 老人端路线

这个分支**只做 Qt/QML 老人端**：

- `qt/`：可编译的 Qt 6 客户端骨架（六页界面、规则展开、**本地 SQLite 主副本**、**端上 30 秒 tick**、`/v1/*` 对接层）
- `server/`：它要连的后端（零第三方依赖，含 `/v1/*` 适配层）
- `integration/yiban_client/`：给正式客户端仓库（`fspro7967/yiban_android_app`）的补丁

**没有 Flutter、没有硬件固件与系统改造脚本**——那些在 `main` 与其他归档分支里。
以后 Qt 路线的迭代都在这个分支做。

## 1. 跑后端

```bash
cd server
python3 server.py --port 8400
python3 test_v1.py            # 手机端契约 9 项（先起服务）
```

## 2. 跑 Qt 端（需要 Qt 6.5+）

```bash
cd qt
cmake -S . -B build -DCMAKE_PREFIX_PATH=/opt/Qt/6.11.1/gcc_64
cmake --build build -j6
CAREMATE_API=http://127.0.0.1:8400 CAREMATE_TOKEN=app-elder-001 ./build/appCareMate
# 只看离线演示：
CAREMATE_OFFLINE=1 ./build/appCareMate
```

Android：换 `-DCMAKE_TOOLCHAIN_FILE=.../android_arm64_v8a/lib/cmake/Qt6/qt.toolchain.cmake`

## 3. 这个分支里有什么

| 路径 | 作用 |
|---|---|
| `qt/core/ReminderModel.*` | 规则 → 实例、状态机、事件队列、端上 tick |
| `qt/core/LocalStore.*` | 本地主副本（SQLite：plans/occurrences/events + 游标），1 秒防抖落盘 |
| `qt/net/HttpClient.*` | 唯一 HTTP 出口（`/v1/*`，令牌与地址三级解析） |
| `qt/net/SyncPuller.*` | 拉计划/状态、推事件、呼救上报、离线退避 |
| `qt/pages/*.qml` | 今日、记录、家人、SOS 四个页面 |
| `qt/android/` | JNI 精确闹钟（`AlarmBridge`）与清单 |
| `integration/yiban_client/` | 正式客户端补丁（`git am` 可用） |
| `server/` | 后端：三档升级链 + `/v1/*` + 九套验收 |
| `tools/` | `verify_all.py`（21 项）、`publish.py`（验证+提交+推送） |

## 4. 改完怎么发

```bash
python tools/publish.py        # 验证 21 项 → 逐文件提交 → 推送**当前分支**（qt）
```

## 5. 验证边界（如实说明）

| 项 | 状态 |
|---|---|
| 后端九套验收 | ✅ 本分支可跑（`python tools/verify_all.py`） |
| `/v1/*` 契约（手机端） | ✅ `server/test_v1.py` 9 项 |
| Qt 端能否编译 | ❌ 需要装了 Qt 6.5+ 的机器；CI 里不编译 Qt |
| 真机锁屏提醒 | ❌ 未验证（需真机与 Qt for Android kit） |

## 6. 与其它分支的关系

| 分支 | 内容 |
|---|---|
| `main` | 整合版：网页端 + Qt 骨架 + Flutter 验证版 + 硬件 |
| `web` | 只做网页端，网页迭代在那里 |
| **`qt`（本分支）** | **只做 Qt 老人端**，Qt 迭代在这里 |
| `v1-web` / `v2-qt` / `v3-flash` | 历史归档（只读） |