#!/system/bin/sh
# 开机后执行（Magisk late_start service）：把 kiosk 相关设置固化下来
# 任何一步失败都不影响开机，逐条 || true

PKG=com.caremate.caremate
LOG=/data/local/tmp/caremate-service.log
echo "[$(date)] service.sh start" >> $LOG

# 1) Doze 白名单：息屏后提醒不漂移
cmd deviceidle whitelist +$PKG >> $LOG 2>&1 || true

# 2) 精确闹钟 + 通知权限（priv-app 已预授予，这里再兜一层）
appops set $PKG SCHEDULE_EXACT_ALARM allow >> $LOG 2>&1 || true
cmd appops set $PKG POST_NOTIFICATION allow >> $LOG 2>&1 || true

# 3) 免打扰穿透（呼救渠道 bypassDnd 需要它）
appops set $PKG ACCESS_NOTIFICATION_POLICY allow >> $LOG 2>&1 || true

# 4) 隐藏状态栏与导航栏（沉浸式）
settings put global policy_control immersive.full=* >> $LOG 2>&1 || true

# 5) 关掉自动时间（演示时防止被改时间导致混乱；需要时手动开）
# settings put global auto_time 0

echo "[$(date)] service.sh done" >> $LOG