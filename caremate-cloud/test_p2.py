# -*- coding: utf-8 -*-
# 作用：令牌与权限 9 项：配对换令牌、越权访问、一次性规则、角色边界
"""P1/P2 验收：配对码换 token、会话隔离、one-off 规则。"""

import json
import urllib.error
import urllib.request

API = "http://127.0.0.1:8400"
FAM, COMM = "fam-demo-2026", "comm-demo-2026"
OUT = []


def call(path, token=None, data=None, method=None):
    req = urllib.request.Request(
        API + path,
        data=None if data is None else json.dumps(data, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json", "X-Forwarded-For": "198.51.100.11", **({"X-Token": token} if token else {})},
        method=method or ("GET" if data is None else "POST"))
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def items_of(body):
    if isinstance(body, list):
        return body
    return body.get("items", []) if isinstance(body, dict) else []


def check(name, ok, detail):
    OUT.append((name, ok, detail))


# 1) 配对码 → 会话令牌
code, r = call("/api/v1/auth/pair", None, {"code": "8823", "label": "验收"})
tok = r.get("token", "")
check("配对码换 token", code == 201 and tok.startswith("ses-"),
      "HTTP %d, token=%s…, 绑定 %s" % (code, tok[:12], r.get("elder_id")))

# 2) 新令牌能读写自己的老人
code, ov = call("/api/v1/overview?user_id=u-elder", tok)
check("会话令牌可访问绑定的老人", code == 200, "HTTP %d，实例 %d 条" % (code, len(ov.get("occurrences", []))))

code, me = call("/api/v1/me", tok)
check("会话令牌可读到自己的身份", code == 200 and me.get("paired_elder") == "u-elder",
      "role=%s, paired_elder=%s" % (me.get("role"), me.get("paired_elder")))

# 3) 会话令牌不能越界
code, _ = call("/api/v1/overview?user_id=u-other", tok)
check("会话令牌访问别的老人被拒", code == 403, "HTTP %d" % code)

# 4) 错误配对码
code, _ = call("/api/v1/auth/pair", None, {"code": "0000"})
check("错误配对码 404", code == 404, "HTTP %d" % code)

# 5) 社区令牌仍然只读
code, _ = call("/api/v1/plans", COMM, {"user_id": "u-elder", "title": "x", "times": ["09:00"]})
check("社区令牌建计划 403", code == 403, "HTTP %d" % code)

# 6) one-off 规则只在那一天生成实例
import datetime
d = (datetime.date.today() + datetime.timedelta(days=3)).isoformat()
code, r = call("/api/v1/plans", FAM, {"user_id": "u-elder", "title": "复诊一次",
                                      "kind": "activity", "times": ["09:30"],
                                      "rule": {"kind": "once", "date": d}})
pid = r.get("id")
code2, occ = call("/api/v1/occurrences?user_id=u-elder&date=%s" % d, FAM)
hits = [o for o in occ if o["plan_id"] == pid]
code3, occ_today = call("/api/v1/occurrences?user_id=u-elder", FAM)
today_hits = [o for o in occ_today if o["plan_id"] == pid]
check("one-off 只在指定日生成", code == 201 and len(hits) == 1 and not today_hits,
      "指定日 %d 条、今天 %d 条（日期 %s）" % (len(hits), len(today_hits), d))

# 7) one-off 缺日期要报错
code, r = call("/api/v1/plans", FAM, {"user_id": "u-elder", "title": "没日期",
                                      "times": ["09:30"], "rule": {"kind": "once"}})
check("one-off 缺日期 422", code == 422, "HTTP %d: %s" % (code, r.get("error")))

# 8) 登出后令牌失效
code, _ = call("/api/v1/auth/logout", tok, {})
code2, _ = call("/api/v1/me", tok)
check("登出后令牌失效", code == 200 and code2 == 401, "登出 %d，再用 %d" % (code, code2))

print("=" * 70)
print("P1/P2 验收")
print("=" * 70)
for name, ok, detail in OUT:
    print("%-26s | %s | %s" % (name, "PASS" if ok else "FAIL", detail))
print("\n总计：%d/%d 通过" % (sum(1 for o in OUT if o[1]), len(OUT)))
json.dump([{"item": n, "ok": o, "detail": d} for n, o, d in OUT],
          open(r"C:\Users\43915\Documents\deepseek-harness\default-workspace\caremate-cloud\acceptance_p2.json",
               "w", encoding="utf-8"), ensure_ascii=False, indent=2)
