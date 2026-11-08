#!/usr/bin/env bash
# 作用：预检：确认演示机是否已 root、包是否已装、精确闹钟权限状态
# 00 预检：确认这台机器是不是"那台 root 的演示机"
set -uo pipefail
echo "== 设备"; adb devices
echo "== root"; adb shell id | grep -q "uid=0" && echo "  已 root" || echo "  未 root（后面 10/20/30 会失败）"
echo "== 型号"; adb shell getprop ro.product.model
echo "== 系统"; adb shell getprop ro.build.version.release
echo "== 包是否安装"; adb shell pm list packages | grep -i caremate || echo "  未安装"
echo "== 精确闹钟权限"; adb shell appops get com.caremate.app SCHEDULE_EXACT_ALARM || true
