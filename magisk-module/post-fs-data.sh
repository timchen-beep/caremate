#!/system/bin/sh
# 作用：开机早期：修正 priv-app 目录权限（部分 ROM 会校验 SELinux 上下文）
# 早期执行：确保 priv-app 目录权限正确（部分 ROM 会校验 SELinux 上下文）
chmod 755 /system/priv-app/CareMate 2>/dev/null || true
chmod 644 /system/priv-app/CareMate/CareMate.apk 2>/dev/null || true