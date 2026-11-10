# -*- coding: utf-8 -*-
# 作用：跑九套验收并把结果汇总成一份 markdown 证据文件
"""证据包：跑六套验收 + 抓关键数字，生成 evidence/验收汇总_日期.md（第 10 步用）。"""

import json
import os
import subprocess
import sys
from datetime import date

BASE = r"C:\Users\43915\Documents\deepseek-harness\default-workspace"
CLOUD = os.path.join(BASE, "caremate-cloud")
PY = sys.executable
SUITES = ["test_contract", "test_accept", "test_p2", "test_v06", "test_align", "test_steps"]

lines = ["# CareMate 验收汇总（%s）" % date.today().isoformat(), ""]

version = "?"
try:
    with open(os.path.join(CLOUD, "server.py"), encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("VERSION ="):
                version = line.split("=")[1].strip().strip('"')
                break
except OSError:
    pass

lines.append("后端：`server.py` v%s ｜ 生成方式：`python collect_evidence.py`" % version)
lines.append("")
lines.append("| 套件 | 覆盖 | 结果 |")
lines.append("|---|---|---|")

coverage = {
    "test_contract": "手机端对接契约 v0.1 七条 + 认证 + 错误码",
    "test_accept": "4.2.6 五条（接口延迟、重放、10 次重启、403、升级）",
    "test_p2": "配对换 token、越界、one-off、登出",
    "test_v06": "派发延迟、事件前后状态、限速、507、备份",
    "test_align": "from/to、历史不变、换时区不重复、单入口",
    "test_steps": "呼救、5 秒撤销、记录撤销留痕、无动静告警",
}

total_ok, total_all = 0, 0
details = []
for suite in SUITES:
    path = os.path.join(CLOUD, suite + ".py")
    if not os.path.exists(path):
        continue
    proc = subprocess.run([PY, "-X", "utf8", path], cwd=CLOUD, capture_output=True, text=True,
                          env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    out = (proc.stdout or "") + (proc.stderr or "")
    summary = ""
    for line in out.splitlines():
        if "总计：" in line:
            summary = line.strip()
    nums = summary.replace("总计：", "").replace(" 通过", "").split("/")
    try:
        ok, tot = int(nums[0]), int(nums[1])
    except Exception:
        ok, tot = 0, 0
    total_ok += ok
    total_all += tot
    lines.append("| `%s.py` | %s | %s |" % (suite, coverage.get(suite, ""),
                                            summary.replace("总计：", "") if summary else "未取到结果"))
    details.append((suite, out))

lines.append("")
lines.append("**合计 %d/%d 通过。**" % (total_ok, total_all))
lines.append("")
lines.append("## 关键数字")
lines.append("")
for suite, out in details:
    for line in out.splitlines():
        if "PASS" in line and ("p95" in line or "p50" in line or "重启" in line or "幂等" in line
                               or "回补" in line or "派发" in line):
            lines.append("- " + line.strip())
lines.append("")
lines.append("## 复现命令")
lines.append("")
lines.append("```bat")
lines.append("cd /d F:\\ppt\\caremate-cloud")
lines.append("python server.py --port 8000")
lines.append("python collect_evidence.py")
lines.append("```")
lines.append("")
lines.append("> 验收用默认阈值 2/5/15（2 分钟没确认 → 通知家属，5 分钟 → 再提醒一次，15 分钟 → 记未确认）；`--demo` 会把阈值设成 1/3/10、等会儿 5 分钟，**只用于演示**（口径不同，别混用）。")

outdir = os.path.join(BASE, "evidence")
os.makedirs(outdir, exist_ok=True)
outfile = os.path.join(outdir, "验收汇总_%s.md" % date.today().strftime("%Y%m%d"))
with open(outfile, "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines))
print("wrote:", outfile)
print("\n".join(lines[:10]))

