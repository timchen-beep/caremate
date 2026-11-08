#!/usr/bin/env bash
# 作用：四种异常一键复现：断网 / 重启 / 改时间 / 连点，用于验收
# 四种异常一键复现（验收用）
set -uo pipefail
CASE="${1:-offline}"
PKG=com.caremate.caremate

case "$CASE" in
  offline)
    adb shell svc wifi disable; adb shell svc data disable
    echo "已断网，60 秒后恢复"; sleep 60
    adb shell svc wifi enable; adb shell svc data enable ;;
  reboot)
    adb reboot; adb wait-for-device
    echo "重启完成：检查未完成的提醒是否自己回来（应在 60 秒内）" ;;
  time-skew)
    adb shell settings put global auto_time 0
    adb shell date "$(date -d '-1 hour' '+%m%d%H%M%Y.%S')"; sleep 5
    adb shell date "$(date -d '+1 day'  '+%m%d%H%M%Y.%S')"; sleep 5
    adb shell settings put global auto_time 1
    echo "改时间完成：检查是否有重复提醒、倒计时是否为负" ;;
  tap-spam)
    for i in $(seq 1 10); do adb shell input tap 206 520; done
    echo "连点 10 次完成：检查服务端是否只记 1 条" ;;
  *) echo "用法: $0 [offline|reboot|time-skew|tap-spam]" ;;
esac