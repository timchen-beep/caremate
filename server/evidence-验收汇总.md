<!-- 作用：七套验收的汇总证据：命令、时间、通过数（由 tools/collect_evidence.py 生成） -->
# CareMate 验收汇总（2026-11-05）

后端：`server.py` v0.9.1 ｜ 生成方式：`python collect_evidence.py`

| 套件 | 覆盖 | 结果 |
|---|---|---|
| `test_contract.py` | 手机端对接契约 v0.1 七条 + 认证 + 错误码 | 18/18 通过 |
| `test_accept.py` | 4.2.6 五条（接口延迟、重放、10 次重启、403、升级） | 6/6 通过 |
| `test_p2.py` | 配对换 token、越界、one-off、登出 | 9/9 通过 |
| `test_v06.py` | 派发延迟、事件前后状态、限速、507、备份 | 7/7 通过 |
| `test_align.py` | from/to、历史不变、换时区不重复、单入口 | 9/9 通过 |
| `test_steps.py` | 呼救、5 秒撤销、记录撤销留痕、无动静告警 | 7/7 通过 |

**合计 56/56 通过。**

## 关键数字

- P95 延迟 ≤ 5 s | PASS | p50 31 ms / p95 35 ms / p99 36 ms（n=100）
- 断网 3 条回补     | PASS | 库里 3 条（应 3），重复提交被识别 3 次
- 10 次强制重启     | PASS | 实例数 13 → 13，异常 0 次
- 调度器自动派发                  | PASS | 状态 notified（阈值 0 分钟，等 ≤130 s）
- 派发延迟 P95 ≤ 30 s          | PASS | p50 4.0 s / p95 4.0 s / max 4.0 s（样本 1，补扫排除 3）

## 复现命令

```bat
cd /d F:\ppt\caremate-cloud
python server.py --port 8000
python collect_evidence.py
```

> 验收用默认阈值 2/15（2 分钟没确认 → 通知家属，15 分钟 → 记未确认）；`--demo` 会把阈值设成 1/3/10、等会儿 5 分钟，**只用于演示**（口径不同，别混用）。

