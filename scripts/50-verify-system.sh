#!/usr/bin/env bash
# 作用：系统改造 8 项自检：priv-app、精确闹钟、通知、Doze、默认桌面、状态栏、进程、AlarmManager
# 系统改造自检：8 项逐条打勾
set -uo pipefail
PKG=com.caremate.caremate
pass=0; fail=0
# 函数 ok：打印通过项并累加通过计数
ok()   { echo "  [OK]   $1"; pass=$((pass+1)); }
# 函数 bad：打印失败项并累加失败计数
bad()  { echo "  [FAIL] $1"; fail=$((fail+1)); }

echo "== CareMate 系统改造自检 =="

# 1 是否装成特权应用
if adb shell pm path $PKG | grep -q "/system/priv-app"; then ok "priv-app 安装"; else bad "priv-app 安装（仍在 /data/app）"; fi

# 2 精确闹钟权限
if adb shell appops get $PKG SCHEDULE_EXACT_ALARM 2>/dev/null | grep -q allow; then ok "精确闹钟 allow"; else bad "精确闹钟未授权"; fi

# 3 通知权限
if adb shell dumpsys package $PKG | grep -q "POST_NOTIFICATIONS: granted=true"; then ok "通知权限"; else bad "通知权限未授予"; fi

# 4 Doze 白名单
if adb shell dumpsys deviceidle whitelist | grep -q $PKG; then ok "Doze 白名单"; else bad "不在 Doze 白名单"; fi

# 5 是否设为默认桌面
HOME_ACT=$(adb shell cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.HOME | tail -1)
case "$HOME_ACT" in *"$PKG"*) ok "默认桌面 = CareMate（$HOME_ACT）";; *) bad "默认桌面不是 CareMate（$HOME_ACT）";; esac

# 6 状态栏隐藏
if adb shell settings get global policy_control | grep -q immersive; then ok "状态栏隐藏(immersive)"; else bad "状态栏未隐藏"; fi

# 7 开机自启（查看 boot 后是否在运行）
if adb shell pidof $PKG >/dev/null 2>&1; then ok "进程在运行"; else bad "进程未运行"; fi

# 8 到期闹钟是否登记
if adb shell dumpsys alarm | grep -q $PKG; then ok "AlarmManager 已登记提醒"; else bad "AlarmManager 无本应用条目"; fi

echo
echo "结果：通过 $pass 项，失败 $fail 项"
[ "$fail" -eq 0 ] && echo "可以演示" || echo "先修失败项，再演示"

