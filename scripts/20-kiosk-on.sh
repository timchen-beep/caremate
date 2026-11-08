#!/usr/bin/env bash
# 作用：开启专注模式：设为默认桌面、隐藏状态栏导航栏、屏幕常亮
# 开启 kiosk：桌面替换 + 状态栏隐藏 + 常亮
# 注意：先跑 30-kiosk-off 确认能恢复，再上演示
set -uo pipefail
PKG=com.caremate.caremate

echo "== 1 设为 Home（默认桌面）"
adb shell cmd package set-home-activity $PKG/.MainActivity 2>/dev/null || \
  adb shell cmd package set-home-activity $PKG/io.flutter.embedding.android.FlutterActivity 2>/dev/null || \
  echo "  设置失败：请在「设置→应用→默认应用→主屏幕」里手动选 CareMate"

echo "== 2 隐藏状态栏与导航栏"
adb shell settings put global policy_control immersive.full=*

echo "== 3 屏幕常亮（充电时）"
adb shell svc power stayon true

echo "== 4 关自动时间（可选，防演示被改时间）"
adb shell settings put global auto_time 0 || true

echo "== 完成。按 Home / 返回 应回不到桌面。恢复执行 30-kiosk-off.sh"