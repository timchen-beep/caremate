<!-- 作用：项目总览：架构、目录、九条分支、怎么迭代（web/qt + 合并）、快速开始、验收、设计取舍、已知限制 -->
# CareMate · 独居老人生活助手

> 老人端 App + 家属 Web 看板 + 一个云端服务。提醒到点必响，未确认会升级，家属随时可看。

课程项目 **CareMate** 的完整源码：可运行的后端与看板、**Qt/QML 老人端（4.1 的交付物）**、早期 Flutter 验证版、
硬件接入与系统级 kiosk 脚本，外加一套"改完自动验证并发布"的工具链。

## 它解决什么

独居老人最常见的两个问题：**忘了吃药** 和 **没人知道他忘没忘**。所以系统做三件事：

1. **提醒在手机上独立成立**：本地闹钟 + 锁屏通知，断网、飞行模式照响（不依赖服务器）
2. **未确认会升级**：到点提醒 → 2 分钟未确认通知家属 → 5 分钟再提醒一次 → 15 分钟记"未确认"，由云端调度器驱动，**不依赖任何页面打开**
3. **家属能看到**：Web 看板实时显示完成情况、告警，呼救 1 秒内弹红条

## 架构

```
[老人手机 Qt/QML App]                  [家属 Web 看板]
  本地 SQLite 主副本                     浏览器即可，无需安装
  端上 30 秒 tick · 离线队列      ▲
        │ HTTPS（JSON，/v1/* 契约）│ 长轮询（告警 <1s 到达）
        ▼                        │
  ┌──────────────────────────────┴─────────┐
  │ 云端：Python 3 标准库 + SQLite（零依赖） │
  │ plan → occurrence → event → outbox     │
  │ transition() 唯一改状态；30s 调度器     │
  │ /api/v1/* 给网页，/v1/* 给手机（同一真相）│
  └──────────────────┬─────────────────────┘
                     │ MQTT（可选）
              [树莓派 broker + ESP32 雷达]
```

## 目录

| 目录 | 内容 |
|---|---|
| `server/` | Python 后端、三个网页（老人端/看板/kiosk）、PWA、九套验收、`/v1/*` 适配层 |
| `qt/` | **Qt/QML 老人端（4.1 交付路线）**：本地 SQLite 主副本 + 端上 tick + `/v1/*` 对接层 |
| `app/` | Flutter 老人端（**早期验证版，非交付物**）：先跑通本地三表 + 端上 30 秒 tick |
| `integration/` | 给正式客户端仓库（`fspro7967/yiban_android_app`）的补丁与改动说明 |
| `pi/` | 树莓派/香橙派部署：mosquitto 配置、systemd、零依赖 MQTT 桥 |
| `scripts/` | 系统改造脚本：priv-app 安装、kiosk 开关、chaos 复现、8 项自检 |
| `device/` | 刷机方向：选机对照、刷 LineageOS、回滚 |
| `magisk-module/` | 可整体禁用的 kiosk 定制层 |
| `docs/` | 接口口径、手机端对接、验收清单、部署、演示脚本、4.2 报告正文 |
| `tools/` | 全量验证、一键发布、分支同步、分支合并、索引生成、P95 采样、证据汇总 |

## 分支：两个迭代分支 + 一个整合分支 + 六个归档

> **网页端迭代在 `web`，Qt 老人端迭代在 `qt`，`main` 只做整合。**

| 分支 | 文件数 | 是什么 | 什么时候看它 |
|---|---|---|---|
| [`main`](../../tree/main) | 154 | 整合版：网页端 + Qt 骨架 + Flutter 验证版 + 硬件脚本 | 交付与答辩用这个 |
| [`web`](../../tree/web) | 49 | **网页端迭代分支**：只有后端 + 三个网页 + PWA + 九套验收 | 改网页端就来这里 |
| [`qt`](../../tree/qt) | 75 | **Qt 老人端迭代分支**：`qt/` 客户端 + 后端 + 对接补丁 | 改 Qt 端就来这里 |
| [`v1-web`](../../tree/v1-web) | 64 | 归档：最早的纯 Web 实现（后端 + 看板 + PWA） | 对照"纯 Web 长什么样" |
| [`v2-qt`](../../tree/v2-qt) | 70 | 归档：Qt/QML 老人端 + 树莓派 broker + ESP32 雷达 + root 安卓 | 对照课程文档的 Qt 路线 |
| [`v3-flash`](../../tree/v3-flash) | 61 | 归档：LineageOS + Magisk kiosk 定制层 + 8 项系统自检 | 需要"只有这一个 App"的设备级演示 |
| [`v1-web-core`](../../tree/v1-web-core) | 42 | 归档核心版：只留实现代码，无文档/APK/测试产物 | 想读代码、复用某一块 |
| [`v2-qt-core`](../../tree/v2-qt-core) | 52 | 归档核心版 | 同上 |
| [`v3-flash-core`](../../tree/v3-flash-core) | 45 | 归档核心版 | 同上 |

### 每条分支里有什么（找不到文件时看这张表）

| 想看什么 | 去哪个分支的哪个目录 |
|---|---|
| 后端 + 家属看板 | 任意分支的 `server/`（v1 叫 `caremate-cloud/`，v2/v3 叫 `legacy-web/`） |
| Qt 老人端 | `main`/`qt` 的 `qt/`；`v2-qt` 的 `app-qt/` |
| Flutter 老人端（验证版） | `main` 的 `app/`、`v1-web` 的 `caremate_app/` |
| 手机端对接补丁 | `main`/`qt` 的 `integration/yiban_client/` |
| 树莓派 / 香橙派部署 | `main`、`v2-qt`、`v2-qt-core` 的 `pi/` |
| 雷达固件 | `main` 的 `server/firmware/`、`v2-qt` 的 `esp32/` |
| 系统改造脚本 | `main`、`v3-flash`、`v3-flash-core` 的 `scripts/` |
| Magisk 定制层 | `main`、`v3-flash`、`v3-flash-core` 的 `magisk-module/` |
| 刷机与回滚 | `main`、`v3-flash`、`v3-flash-core` 的 `device/` |

> 归档分支历史互不相关，`git switch v2-qt` 会**整体替换工作区**（看着像项目变了），看完记得切回来。
> 只想看代码就在网页上点分支切换，别在本地切。

## 怎么迭代（改完自动发布）

```bash
# 1) 改网页端：在 web 分支上干活
git checkout web
#   …改代码…
python tools/publish.py            # 验证 21 项 → 逐文件提交 → 推送 web

# 2) 改 Qt 老人端：在 qt 分支上干活
git checkout qt
python tools/publish.py            # 同样自动推 qt

# 3) 后端改完后，把 server/ 补到另一条迭代分支
python tools/sync_branches.py --only qt      # 或 --only web

# 4) 定期把两个分支的成果合回整合版
git checkout main
python tools/merge_from_branches.py
```

| 工具 | 干什么 |
|---|---|
| `tools/verify_all.py` | 21 项全量验证（截断、二进制、语法、服务、九套验收、产物卫生、构建引用、页面、文档数字） |
| `tools/publish.py` | 验证 → 逐文件提交 → 推送**当前分支**（验证不过不提交） |
| `tools/sync_branches.py` | 把 `server/` 核心同步到 `web`/`qt`/六条归档分支（起服务验证后提交推送） |
| `tools/merge_from_branches.py` | 在 `main` 上按归属把 `web`/`qt` 拉回来（不删除 main 独有文件） |
| `tools/gen_index.py` | 生成 `FILES.md` / `FUNCTIONS.md` |
| `tools/sample_p95.py` | 取 P95 真实样本（对齐下一分钟 + 等调度） |
| `tools/collect_evidence.py` | 跑九套验收并汇总成证据文件 |

> 详细规约见 [CONTRIBUTING.md](CONTRIBUTING.md)：三条铁律、迭代流程、分支归属、14 条踩过的坑。

## 代码怎么看

| 文件 | 内容 |
|---|---|
| [`GUIDE.md`](GUIDE.md) | **第一次看这个项目先读它**：四个核心概念、一条数据流、阅读顺序、改功能改哪里 |
| [`FILES.md`](FILES.md) | 每个文件是干什么的（154 个文件） |
| [`FUNCTIONS.md`](FUNCTIONS.md) | 每个函数是干什么的（142 个函数） |

每个代码文件第一行都有 `作用：…` 注释；每个函数上方有 `函数 X：…` 注释——索引就是从这些注释生成的。

## 快速开始（3 条命令）

```bash
cd server
python3 server.py --port 8000
# 浏览器打开 http://127.0.0.1:8000/dashboard
```

| 页面 | 地址 | 用途 |
|---|---|---|
| 首页 | `/` | 入口与健康检查 |
| 老人端 | `/app` | 四个大按钮（确认/稍后/记录/呼救） |
| 家属看板 | `/dashboard` | 今日进度、告警、统计、计划管理 |
| 大屏 kiosk | `/kiosk` | 只有这一个 App 的设备级演示 |

默认账号（**仅本地演示**，上公网前必须改）：

| 角色 | 令牌 |
|---|---|
| 老人 | `app-elder-001` |
| 家属 | `fam-demo-2026` |
| 社区 | `comm-demo-2026` |

配对码 `8823`。

## 验收

一条命令跑全部：

```bash
python tools/verify_all.py            # 21 项
python tools/verify_all.py --flutter  # 额外跑 flutter analyze
```

分套跑（在 `server/` 下）：

| 脚本 | 内容 |
|---|---|
| `test_contract.py` | 契约 18 项 |
| `test_accept.py` | 可靠性 6 项（重启、离线补传、调度升级） |
| `test_align.py` | 一致性 9 项（改计划不改历史、换时区不新增） |
| `test_p2.py` | 令牌/权限/一次性规则 9 项 |
| `test_steps.py` | 呼救/撤销/无动静 7 项 |
| `test_v06.py` | 派发延迟/限速/磁盘水位/备份 7 项 |
| `test_extra.py` | 扩展 7 项 |
| `test_sync.py` | 端云同步 5 项 |
| `test_v1.py` | 手机端 v1.1 契约 9 项 |

> `test_accept.py` 与 `test_v1.py` 需要**先有服务在跑**；`verify_all.py` 会自己起。

## Qt 老人端（4.1 的交）

```bash
cd qt
cmake -S . -B build -DCMAKE_PREFIX_PATH=/opt/Qt/6.11.1/gcc_64
cmake --build build -j6
CAREMATE_API=http://127.0.0.1:8400 CAREMATE_TOKEN=app-elder-001 ./build/appCareMate
CAREMATE_OFFLINE=1 ./build/appCareMate     # 只看离线演示
```

正式客户端在 [`fspro7967/yiban_android_app`](https://github.com/fspro7967/yiban_android_app)，
接本后端的补丁在 `integration/yiban_client/对接后端.patch`（`git am` 即可）。

## 设计取舍（答辩会被问）

| 取舍 | 理由 |
|---|---|
| 4.1 用 Qt/QML | 4.1 由 app 组按 Qt 路线实现（架构图与仓库均为 Qt）；Flutter 版只用于先验证本地主副本与端上 tick |
| 状态以云端为准 | "提醒不丢不重"的前提；手机端保留本地副本只为离线可读 |
| 调度器放两处 | 端上 tick 保证离线也到点响；云端 scheduler 兜底升级与 missed |
| 云端单进程 | 两个 worker 会有两个调度循环，提醒发两遍 |
| 不做电话/短信 | 需要运营商资质与费用；通道预留 Webhook |
| 不做医疗判断 | 只提示"请联系家属/医生"，不给补服建议 |

## 已知限制（如实说明）

1. Qt 老人端**未在本机编译**（无 Qt kit）；真机锁屏通知、精确闹钟待实测。
2. 正式客户端仓库**未打补丁**（补丁已备好，需有写权限的人 `git am`）。
3. Flutter 验证版能出签名 APK，但**未在真机安装验证**。
4. MQTT 桥与 ESP32 固件已写，**未连真实 broker / 未烧录**。
5. 刷机与系统改造脚本**未在真机执行**。
6. 部署脚本未在真实服务器跑过。

## License

MIT
