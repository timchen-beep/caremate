# -*- coding: utf-8 -*-
# 作用：推送助手：代理没开时先试直连，最后给出"代理未启动"的明确提示，而不是干等 5 分钟
"""push 的统一入口（publish / merge_from_branches 共用）。

为什么单独抽出来：之前 `git push` 在代理关掉时会挂在 TCP 连接上**5 分钟**才超时，
中间没有任何提示；而直连 GitHub 在国内通常被重置。这里按顺序尝试并快速失败：

    1. 正常 push（走 git 配置的代理）
    2. 若报代理相关错误 → 先看 127.0.0.1:7890 是否在监听
         - 没在监听 → 直接试一次"禁用代理"的 push（有些网络能直连）
         - 都在监听但失败 → 再重试 2 次（网络抖动）
    3. 全失败 → 返回一句可操作的话，而不是堆栈
"""

import socket
import subprocess
import time

PROXY_HOST, PROXY_PORT = "127.0.0.1", 7890


def proxy_listening(host=PROXY_HOST, port=PROXY_PORT, timeout=0.4):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _git(args, cwd, timeout):
    try:
        return subprocess.run(["git", "-C", cwd, "-c", "core.quotepath=false"] + args,
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        class _Timeout:
            returncode = 124
            stdout = ""
            stderr = "连接超时（%d 秒）" % timeout
        return _Timeout()


def push(branch, cwd, attempts=3, quick_timeout=90):
    """推送 branch；返回 (ok, message)。"""
    # 1) 正常推（走配置里的代理）
    result = _git(["push", "origin", branch], cwd, quick_timeout)
    if result.returncode == 0:
        return True, "推送成功（走配置代理/直连）"

    last = (result.stderr or "").strip()[:160]
    looks_proxy = any(k in last.lower() for k in ("proxy", "timed out", "timeout", "unable to access"))

    # 2) 代理没在监听 → 试一次禁用代理的直连
    if looks_proxy and not proxy_listening():
        direct = _git(["-c", "http.proxy=", "-c", "http.https://github.com/.proxy=",
                       "push", "origin", branch], cwd, quick_timeout)
        if direct.returncode == 0:
            return True, "推送成功（禁用代理直连）"
        return False, (
            "推送失败：代理 127.0.0.1:7890 没有在监听，直连 GitHub 也不通。\n"
            "  → 先启动代理（Clash / v2ray 等，混合端口 7890），再重跑：python tools/publish.py"
        )

    # 3) 代理在监听：再重试几次（抖动）
    for i in range(2, attempts + 1):
        time.sleep(5)
        result = _git(["push", "origin", branch], cwd, quick_timeout)
        if result.returncode == 0:
            return True, "推送成功（第 %d 次尝试）" % i
        last = (result.stderr or "").strip()[:160]

    return False, "推送失败（重试 %d 次）：%s" % (attempts, last)
