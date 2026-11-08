# -*- coding: utf-8 -*-
# 作用：调度器手动验证脚本：不碰页面也能自己升级（开发用）
"""验证：不调用任何页面/dev 接口，仅靠服务进程内的 30 s 调度器完成升级。"""
import json
import time
import urllib.request
from datetime import datetime, timedelta

API = "http://127.0.0.1:8400"
FAM = "fam-demo-2026"


def call(path, data=None, token=FAM):
    req = urllib.request.Request(API + path,
                                 data=None if data is None else json.dumps(data).encode(),
                                 headers={"X-Token": token, "Content-Type": "application/json"},
                                 method="GET" if data is None else "POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())


t = (datetime.now() - timedelta(minutes=6)).strftime("%H:%M")
pid = call("/api/v1/plans", {"user_id": "u-elder", "title": "自动调度验证", "kind": "medication",
                             "times": [t], "dose": "1 片", "rule": {"kind": "daily"}})["id"]
print("建计划：6 分钟前 %s（plan %s）" % (t, pid))

occ = [o for o in call("/api/v1/occurrences?user_id=u-elder")["items"] if o["plan_id"] == pid]
print("物化后状态：", occ[0]["state"] if occ else "无实例")

print("现在完全不动手，等 40 秒看服务自己升级……")
for i in range(8):
    time.sleep(5)
    occ = [o for o in call("/api/v1/occurrences?user_id=u-elder")["items"] if o["plan_id"] == pid]
    st = occ[0]["state"] if occ else "?"
    print("  +%2ds  状态=%s  级别=%s  通知时间=%s" %
          ((i + 1) * 5, st, occ[0]["level"], occ[0]["notified_local"] or "-"))
    if st in ("escalated", "missed"):
        break

alarms = call("/api/v1/alarms?user_id=u-elder")["items"]
mine = [a for a in alarms if occ and a["occurrence"] == occ[0]["id"]]
print("\n该实例告警：", [(a["kind"], a["level"], a["created_local"]) for a in mine])
print("结论：", "PASS —— 无人操作也会升级" if occ and occ[0]["state"] in ("escalated", "missed") else "FAIL")

