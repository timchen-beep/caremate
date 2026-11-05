#!/system/bin/sh
# Magisk 安装时执行：把 APK 与权限声明放进 system 分区
SKIPUNZIP=0

ui_print "- 安装 CareMate 特权应用"
if [ ! -f "$MODPATH/system/priv-app/CareMate/CareMate.apk" ]; then
  ui_print "!! 缺少 APK：请把 CareMate-release.apk 放到"
  ui_print "   magisk-module/system/priv-app/CareMate/CareMate.apk 后重新打包"
  abort "! 缺少 APK"
fi

ui_print "- 设置权限"
set_perm_recursive "$MODPATH/system/priv-app/CareMate" 0 0 0755 0644
set_perm "$MODPATH/system/etc/permissions/privapp-permissions-com.caremate.caremate.xml" 0 0 0644

ui_print "- 完成。重启后生效；禁用本模块即可回滚。"