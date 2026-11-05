#!/usr/bin/env bash
# 回滚：把演示机变回普通手机
set -uo pipefail
PKG=com.caremate.caremate

echo "== 1 解除 kiosk"
adb shell settings put global policy_control null || true
adb shell cmd package set-home-activity com.android.launcher3/.Launcher 2>/dev/null || \
  adb shell cmd package set-home-activity com.google.android.apps.nexuslauncher/.NexusLauncherActivity 2>/dev/null || true
adb shell pm enable com.android.launcher3 2>/dev/null || true

echo "== 2 禁用 Magisk 模块（最彻底的开关）"
adb shell "su -c 'touch /data/adb/modules/caremate_kiosk/disable'" || \
  echo "  无 root：请在 Magisk App 里关闭模块后重启"

echo "== 3 卸载特权应用/保留数据"
read -r -p "  要彻底卸载 App 吗？(y/N):" ans
if [ "${ans:-}" = "y" ]; then
  adb shell pm uninstall -k --user 0 $PKG || true
fi

echo "== 4 重启"
adb reboot
echo "重启后检查：桌面回来了、状态栏回来了、能正常装其他 App"