#!/usr/bin/env bash
# 30 把手机变成"只有这一个 App"（可逆）
# 注意：先跑 00-precheck 确认真是演示机，别锁自己的日常机
set -uo pipefail
MODE="${1:-on}"
PKG=com.caremate.app

if [ "$MODE" = "on" ]; then
  echo "== 隐藏状态栏与导航栏（沉浸式）"
  adb shell settings put global policy_control immersive.full=*
  echo "== 设为我们为 Home（无需换 Launcher 也能挡住桌面）"
  adb shell cmd package set-home-activity $PKG/.MainActivity || echo "  set-home-activity 失败，可改用下面禁用原桌面"
  # 有 root 时更彻底：直接停用原桌面
  # adb shell pm disable-user --user 0 com.android.launcher3
  echo "== 锁定任务（可选，部分 ROM 支持）"
  adb shell am task lock 2>/dev/null || true
else
  echo "== 恢复"
  adb shell settings put global policy_control null
  adb shell pm enable com.android.launcher3 2>/dev/null || true
  adb shell cmd package set-home-activity com.android.launcher3/.Launcher 2>/dev/null || true
  adb shell am task lock stop 2>/dev/null || true
fi
echo "完成（$MODE）"
