# -*- coding: utf-8 -*-
# 作用：生成随机令牌与配对码并写入 server/.env（已被 .gitignore 忽略），供上公网时替换演示值
"""令牌轮换工具。

为什么需要：仓库里的 `app-elder-001` / `fam-demo-2026` / `comm-demo-2026` / 配对码 `8823`
是**演示值**，一旦用公网地址暴露（如 Tailscale Funnel），等于谁都能登。

用法：

    python tools/rotate_tokens.py            # 生成新值，写 server/.env，并打印
    python tools/rotate_tokens.py --print    # 只打印当前 .env 里的值
    python tools/rotate_tokens.py --dry-run  # 只生成看结果，不写文件

    # 想短一点、好念一点（去掉 0O1Il 这类易混字符，8 位）：
    python tools/rotate_tokens.py --easy --length 8

    # 想让家属/老人不用抄令牌：发带 token 的链接，点开自动填好并抹掉地址栏
    #   http://<服务器>/dashboard?token=<家属令牌>
    #   http://<服务器>/app?token=<老人令牌>&base=http://<服务器>

长度怎么选：24 位以上基本不可猜；`--easy --length 8` 约 40 bit，抗在线爆破够用
（配合 /v1/pair 的 10 次/10 分钟限速），但**别把 6 位的当安全令牌**——6 位数字
一秒钟能试好几万次，只适合配对码这种一次性短码。

生成后需要重启服务（`server/start-caremate.bat` 会自动读取 .env）。
"""

import argparse
import io
import os
import secrets
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(ROOT, "server", ".env")
KEYS = ("CAREMATE_ELDER_TOKEN", "CAREMATE_FAMILY_TOKEN", "CAREMATE_COMMUNITY_TOKEN")


def read_env():
    if not os.path.isfile(ENV_PATH):
        return {}
    data = {}
    with io.open(ENV_PATH, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            data[key.strip()] = value.strip()
    return data


def main():
    ap = argparse.ArgumentParser(description="生成随机令牌，写入 server/.env")
    ap.add_argument("--print", dest="show", action="store_true", help="只打印现有值")
    ap.add_argument("--dry-run", action="store_true", help="不写文件")
    ap.add_argument("--length", type=int, default=32, help="令牌长度，默认 32 位")
    ap.add_argument("--easy", action="store_true",
                    help="只用不易看错的字符（去掉 0 O 1 I l），适合要手抄/口述的场景")
    ap.add_argument("--pair-len", type=int, default=6, help="配对码位数，默认 6")
    args = ap.parse_args()

    # 默认 24 字节的 urlsafe base64 ≈ 32 位；--length 控制位数。
    # --easy 用一套去掉易混字符的字母表：0/O、1/I/l 在纸上和屏幕上都会认错，
    # 老人端要靠家属念/抄令牌，错一位就是 401。
    alphabet = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ" if args.easy else None

    def make(length):
        if alphabet:
            return "".join(secrets.choice(alphabet) for _ in range(length))
        return secrets.token_urlsafe(max(8, length))[:length]

    if args.length < 6:
        print("--length 至少 6 位（再短就接近可猜了）")
        return 2
    if args.easy and args.length < 8:
        print("--easy 模式下建议至少 8 位（32 个字符的字母表，8 位约 40 bit）")
        return 2

    current = read_env()
    if args.show:
        if not current:
            print("还没有 server/.env（当前用的是代码里的演示值）")
            return 0
        for key, value in current.items():
            print("%s=%s" % (key, value))
        return 0

    tokens = {key: make(args.length) for key in KEYS}
    pair_code = "".join(secrets.choice("0123456789") for _ in range(max(4, args.pair_len)))

    # 只替换这四个键，其余键（CAREMATE_DB / CAREMATE_TZ / CAREMATE_JWT_SECRET …
    # 别人手工加的）原样保留：以前整文件重建，一次轮换就把库路径等配置抹掉了。
    keep = [key for key in current if key not in KEYS and key != "CAREMATE_PAIR_CODE"]
    lines = [
        "# 作用：本机私密配置（令牌/配对码）。已在 .gitignore 中忽略，不要提交。",
        "# 由 tools/rotate_tokens.py 生成于 %s" % __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M"),
        "",
        "CAREMATE_ELDER_TOKEN=%s" % tokens["CAREMATE_ELDER_TOKEN"],
        "CAREMATE_FAMILY_TOKEN=%s" % tokens["CAREMATE_FAMILY_TOKEN"],
        "CAREMATE_COMMUNITY_TOKEN=%s" % tokens["CAREMATE_COMMUNITY_TOKEN"],
        "CAREMATE_PAIR_CODE=%s" % pair_code,
    ]
    if keep:
        lines += ["", "# 以下键不是本脚本生成的，原样保留"] + \
                 ["%s=%s" % (key, current[key]) for key in keep]
    lines.append("")
    content = "\n".join(lines)
    if not args.dry_run:
        io.open(ENV_PATH, "w", encoding="utf-8", newline="\n").write(content)
        try:
            os.chmod(ENV_PATH, 0o600)
        except OSError:
            pass
        print("已写入 %s（.gitignore 已忽略）" % ENV_PATH)
    else:
        print("[dry-run] 未写文件，生成结果如下：")

    print("\n=== 新令牌（只显示这一次，请抄到密码管理器）===")
    for label, key in (("老人端", "CAREMATE_ELDER_TOKEN"),
                       ("家属看板", "CAREMATE_FAMILY_TOKEN"),
                       ("社区", "CAREMATE_COMMUNITY_TOKEN")):
        print("  %-8s %s" % (label, tokens[key]))
    print("  %-8s %s" % ("配对码", pair_code))
    print("\n重启服务后生效：server\\start-caremate.bat")
    return 0


if __name__ == "__main__":
    sys.exit(main())
