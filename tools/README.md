<!-- 作用：辅助工具的说明：怎么跑七套验收并生成一份证据文件 -->
# 工具

## collect_evidence.py

跑七套验收，把命令、时间、通过数汇总成一份 markdown 证据（给报告/答辩用）。

```bash
cd server && python server.py --port 8000 &     # 先起服务
python tools/collect_evidence.py                # 生成 evidence/验收汇总_<日期>.md
```

注意：`--demo` 预设会改阈值（1/3/10 分钟），跑验收时**不要**带这个参数，
否则部分套件会因阈值不同而失败。