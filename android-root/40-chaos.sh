#!/usr/bin/env bash
# 40 chaos：把四种"会出事"的情况变成一条命令（验收用）
set -uo pipefail
CASE="${1:-offline}"
PKG=com.caremate.app

case "$CASE" in
  offline)      # 断网 60 秒
    adb shell svc wifi disable; adb shell svc data disable
    echo "已断网，60 秒后自动恢复"; sleep 60
    adb shell svc wifi enable; adb shell svc data enable ;;
  reboot)       # 重启并等回来
    adb reboot; adb wait-for-device
    echo "重启完成，检查未完成提醒是否回来" ;;
  time-skew)    # 时间往前拨 1 小时，再往后拨 1 天
    adb shell settings put global auto_time 0
    adb shell date "$(date -d '-1 hour' '+%m%d%H%M%Y.%S')"
    sleep 5
    adb shell date "$(date -d '+1 day' '+%m%d%H%M%Y.%S')"
    sleep 5
    adb shell settings put global auto_time 1 ;;
  tap-spam)     # 连点 10 次，验证只算一次
    for i in $(seq 1 10); do adb shell input tap 206 520; done ;;
  *) echo "用法: $0 [offline|reboot|time-skew|tap-spam]" ;;
esac
