#!/usr/bin/env bash
# 作用：一键恢复：还原桌面、状态栏、常亮与自动时间（演示前必须先演这一条）
# 一键恢复：演示前必须演一遍这个
set -uo pipefail
PKG=com.caremate.caremate
LAUNCHER_CANDIDATES="com.android.launcher3/.Launcher com.google.android.apps.nexuslauncher/.NexusLauncherActivity com.miui.home/.launcher.Launcher com.oneplus.launcher/.Launcher"

echo "== 1 恢复状态栏与导航栏"
adb shell settings put global policy_control null

echo "== 2 恢复默认桌面（逐个尝试，成功即止）"
for l in $LAUNCHER_CANDIDATES; do
  if adb shell cmd package set-home-activity "$l" 2>/dev/null; then
    echo "  已恢复：$l"; break
  fi
done

echo "== 3 恢复屏幕常亮设置"
adb shell svc power stayon false || true

echo "== 4 恢复自动时间"
adb shell settings put global auto_time 1 || true

echo "== 5 解除任务锁定（如果之前锁过）"
adb shell am task lock stop 2>/dev/null || true

echo "== 完成。检查：桌面图标回来了、能下拉状态栏"

