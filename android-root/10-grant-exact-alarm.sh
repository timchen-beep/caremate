#!/usr/bin/env bash
# 作用：授予精确闹钟权限 + Doze 白名单 + 通知权限（root 机器免手动设置）
# 10 精确闹钟 + 电量白名单（Android 14 新装默认拒绝精确闹钟）
set -uo pipefail
PKG=com.caremate.app
echo "授予 SCHEDULE_EXACT_ALARM"
adb shell appops set $PKG SCHEDULE_EXACT_ALARM allow
echo "加入 Doze 白名单"
adb shell cmd deviceidle whitelist +$PKG
echo "通知权限（Android 13+）"
adb shell pm grant $PKG android.permission.POST_NOTIFICATIONS || true
echo "验证："
adb shell dumpsys alarm | grep -A3 $PKG | head -20 || true

