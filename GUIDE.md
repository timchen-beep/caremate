<!-- 作用：web 分支的阅读指南：从哪读起、改功能改哪里、测试怎么跑 -->
# 网页端路线怎么读、怎么改

## 1. 从哪读起（按顺序）

| 步骤 | 文件 | 看什么 |
|---|---|---|
| 1 | `server/web/dashboard.html` | 家属看到的东西：今日进度、告警、统计 |
| 2 | `server/web/app.html` | 老人看到的四个大按钮 |
| 3 | `server/server.py` 的 `transition()` | 状态怎么变（唯一入口） |
| 4 | `server/server.py` 的 `scheduler_tick()` | 到点提醒与三档升级 |
| 5 | `server/server.py` 的路由段 | 接口清单 |

## 2. 改功能改哪里

| 想改什么 | 改这个文件 |
|---|---|
| 老人端按钮/流程 | `server/web/app.html` |
| 家属看板统计/图表 | `server/web/dashboard.html` |
| 大屏显示 | `server/web/kiosk.html` |
| 提醒规则 / 升级阈值 | `server/server.py` 的 `CONFIG` 与 `slots_on` / `scheduler_tick` |
| 接口字段 | `server/server.py` 的 `occ_view` 与 `docs/接口与指标口径.md`（两处一起改） |

## 3. 测试

```bash
cd server
python3 test_contract.py     # 契约 18 项
python3 test_accept.py       # 可靠性 6 项（含重启、离线补传）
python3 test_align.py        # 一致性 9 项（改计划不改历史）
python3 test_p2.py           # 计划与预览 9 项
python3 test_steps.py        # 实现步骤 7 项
python3 test_v06.py          # 接口补充 7 项
python3 test_extra.py        # 扩展 7 项
python3 test_sync.py         # 端云同步 5 项
python3 test_v1.py           # 手机端契约 9 项
```

注意：`test_accept.py` 与 `test_v1.py` 需要**先有服务在跑**（`python3 server.py --port 8400`）。
一条命令全跑：`python tools/verify_all.py`（会自己起服务）。

## 4. 三个容易踩的坑

1. 改了 `occ_view` 的输出字段，一定要同步 `docs/接口与指标口径.md`，否则文档守卫会报"文档数字一致"失败（数字对不上）。
2. 新增页面要同时注册到 `server.py` 的静态路由，否则 404。
3. 改 `scheduler_tick()` 后必须跑 `test_accept.py`——它的调度用例按分钟造数据。