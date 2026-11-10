<!-- 作用：把颐伴手机端（fspro7967/yiban_android_app）接到本后端的改动包：补丁、说明、应用方法 -->
# 颐伴手机端对接包

这个目录是**对我们后端的主动适配**：不只服务端出接口，还把对方客户端的 HTTP 层与同步层一起补上。

| 文件 | 内容 |
|---|---|
| `对接后端.patch` | 对 `fspro7967/yiban_android_app` 的两个提交（git format-patch，可直接 `git am`） |
| `对接后端_改动说明.md` | 改了什么、怎么配置、验证到哪一步（含"没编译过"的如实说明） |

## 应用方法

```bash
git clone https://github.com/fspro7967/yiban_android_app.git
cd yiban_android_app
git am /path/to/对接后端.patch          # 或 git apply --3way
```

## 改了什么（facade 与 qml/ 一行未改）

| 文件 | 改动 |
|---|---|
| `src/comm/http_client.{h,cpp}` | 新增 `QNetworkHttpClient`（真 `QNetworkAccessManager` 实现，`OfflineHttpClient` 保留） |
| `src/comm/sync_engine.{h,cpp}` | **新增**：拉 `/v1/plans`、`/v1/state`，推 `/v1/events`，配对，指数退避 |
| `src/vm/app_core.{h,cpp}` | 新增 4 个灌入方法：`applyRemotePlans` / `applyRemoteOccurrences` / `pendingEvents` / `markEventsUploaded` |
| `src/vm/sync_vm.{h,cpp}` | `syncState` / `lastSyncTs` / `pendingCount` / `retrySync` 由引擎驱动 |
| `src/vm/device_vm.cpp` | `pair()` 触发 `POST /v1/pair` |
| `CMakeLists.txt` | 加入 `sync_engine` 两个源文件 |

## 配置

```bash
export YIBAN_API=http://<电脑局域网IP>:8400
export YIBAN_TOKEN=app-elder-001
```

## 验证到哪一步

| 项 | 状态 |
|---|---|
| 后端 `/v1/*` 契约 | ✅ `server/test_v1.py` 9 项自动化（CI 里跑） |
| 端上代码编译 | ❌ 本机没有 Qt 6.11 环境，**未编译** |
| 真机联调 | ❌ 未做（需同一局域网 + 真机） |

要做完最后两项，在一台装了 Qt 6.11 的机器上执行 `对接后端_改动说明.md` 里的 cmake 命令即可。