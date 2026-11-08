#!/usr/bin/env bash
# 作用：把 APK 装成系统特权应用（/system/priv-app）并放权限白名单，免授权拿到精确闹钟
# 把 CareMate 装成系统特权应用（不换 ROM 也能做，只需 root）
set -euo pipefail
PKG=com.caremate.caremate
APK="${1:-app/CareMate-release.apk}"

[ -f "$APK" ] || { echo "找不到 APK：$APK"; exit 1; }

echo "== 1 推送到临时目录"
adb push "$APK" /data/local/tmp/CareMate.apk

echo "== 2 复制进 priv-app（需要 root）"
adb shell su -c "mkdir -p /system/priv-app/CareMate"
adb shell su -c "cp /data/local/tmp/CareMate.apk /system/priv-app/CareMate/CareMate.apk"
adb shell su -c "chmod 644 /system/priv-app/CareMate/CareMate.apk"
adb shell su -c "mount -o remount,rw /system 2>/dev/null || true"

echo "== 3 放权限白名单"
adb push magisk-module/system/etc/permissions/privapp-permissions-$PKG.xml /data/local/tmp/
adb shell su -c "mkdir -p /system/etc/permissions"
adb shell su -c "cp /data/local/tmp/privapp-permissions-$PKG.xml /system/etc/permissions/"
adb shell su -c "chmod 644 /system/etc/permissions/privapp-permissions-$PKG.xml"

echo "== 4 重启并验证"
adb reboot
echo "  重启后执行： bash scripts/50-verify-system.sh"

