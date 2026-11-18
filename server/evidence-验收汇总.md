<!-- 作用：十套验收的汇总证据：命令、时间、通过数（由 tools/collect_evidence.py 生成） -->
> 本文件用临时库跑出来的一份留档：`python tools/collect_evidence.py -o server` 可随时重跑覆盖。
> 旧记录（v0.9.1 只有六套）在 git 历史里，不再保留在本文件。

# CareMate 验收汇总（2026-11-18）

后端：`server/server.py` v1.0.0 ｜ 被测地址：http://127.0.0.1:8400

| 套件 | 覆盖 | 结果 |
|---|---|---|
| `test_contract.py` | 手机端对接契约 v0.1 七条 + 认证 + 错误码 | 18/18 通过 |
| `test_p2.py` | 配对换 token、越界、one-off、登出 | 9/9 通过 |
| `test_align.py` | from/to、历史不变、换时区不重复、单入口 | 9/9 通过 |
| `test_steps.py` | 呼救、5 秒撤销、记录撤销留痕、无动静告警 | 7/7 通过 |
| `test_v06.py` | 派发延迟、事件前后状态、限速、507、备份 | 7/7 通过 |
| `test_extra.py` | 越权、导出、告警确认、社区 webhook | 7/7 通过 |
| `test_sync.py` | 端云同步三条接口（上行事件 / 下行增量 / 呼救） | 5/5 通过 |
| `test_v1.py` | 手机族 /v1/* 七个端点与 ID 映射 | 9/9 通过 |
| `test_bridge.py` | MQTT 桥：订阅 presence 转 HTTP + 防回环（假 broker，不装 mosquitto） | 14/14 通过 |
| `test_accept.py` | 4.2.6 五条（接口延迟、重放、10 次重启、403、升级链） | 6/6 通过 |

**合计 91/91 通过。**

## 关键数字

- 调度器自动派发                  | PASS | 状态 escalated（阈值 0 分钟，等 ≤130 s）
- 派发延迟 P95 ≤ 30 s          | PASS | p50 7.0 s / p95 7.0 s / max 7.0 s（样本 1，补扫排除 4）
- 单查询即可解释升级                | PASS | 一次 GET 返回 2 条迁移事件
- --demo 与 --preview 可用        | PASS | 输出首行：演示预设：升级 1/3/10 分钟，等会儿 5 分钟
- 重放幂等（不新增）         | PASS | accepted=0 duplicates=1
- P95 延迟 ≤ 5 s | PASS | p50 31 ms / p95 40 ms / p99 44 ms（n=100）
- 断网 3 条回补     | PASS | 库里 3 条（应 3），重复提交被识别 3 次
- 30 s 调度产生升级  | PASS | 1 分钟→notified、6 分钟→escalated（告警 level [2, 3]）、16 分钟→missed，missed 告警 1 条
- 10 次强制重启     | PASS | 实例数 15 → 15，异常 0 次

## 复现命令

```bash
python server/server.py --port 8400
python tools/collect_evidence.py
```

> 验收用默认阈值 2/5/15 分钟（2 分钟没确认 → 通知家属，5 分钟 → 再提醒一次，15 分钟 → 记未确认）；`--demo` 会把阈值改成 1/3/10、等会儿 5 分钟，**只用于演示**，别和验收混用。