#!/usr/bin/env bash
# 作用：刷机骨架：校验机型、备份 boot/dtbo/vbmeta、解锁、刷官方 LineageOS
# 刷 LineageOS 骨架脚本：每一步都先校验，再执行；失败即停。
# 用法： bash flash-lineage.sh <机型代号> [lineage-*.zip 路径]
set -euo pipefail
CODENAME="${1:?用法: bash flash-lineage.sh <机型代号，如 sunfish> [rom.zip]}"
ROM="${2:-}"

echo "== 0 预检"
adb devices
adb shell getprop ro.product.device | grep -qx "$CODENAME" || {
  echo "!! 机型不符：设备是 $(adb shell getprop ro.product.device)，脚本要的是 $CODENAME"; exit 1; }
echo "  机型 OK：$CODENAME"

echo "== 1 备份原厂分区（务必先做）"
mkdir -p backup
for p in boot dtbo vbmeta system; do
  adb shell su -c "dd if=/dev/block/by-name/$p of=/sdcard/$p.img" 2>/dev/null || \
    echo "  （$p 需要 root；无 root 时跳过，靠官方包回滚）"
  adb pull /sdcard/$p.img backup/ 2>/dev/null || true
done
ls -lh backup || true

echo "== 2 进 fastboot"
adb reboot bootloader
sleep 8
fastboot devices

echo "== 3 解锁（首次需要；会清空数据）"
read -r -p "  已解锁请按回车；未解锁输入 u 继续:" ans
if [ "${ans:-}" = "u" ]; then
  fastboot flashing unlock
  read -r -p "  手机上确认后按回车"
fi

echo "== 4 刷 recovery / boot（按机型不同，此处以 Pixel 为例）"
if [ -n "$ROM" ]; then
  echo "  使用官方 LineageOS 安装流程（fastboot update 或 recovery sideload）"
  echo "  建议：fastboot update $ROM   （部分机型）或 recovery 里 adb sideload"
else
  echo "  未提供 ROM 路径，仅完成解锁与备份。"
fi

echo "== 5 首次开机后回归基线"
echo "  检查：能打电话、相机、WiFi、指纹"
echo "  再执行： scripts/10-privapp-install.sh"