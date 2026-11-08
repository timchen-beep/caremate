<!-- 作用：Magisk 定制层的说明：模块结构、安装方式、为什么能一键回滚 -->
# Magisk 定制层（kiosk）

一个**可整体禁用**的 Magisk 模块：把 CareMate 装成系统特权应用，并在开机时把 kiosk 相关设置固化。

## 结构

```
magisk-module/
├── module.prop                模块元信息（id/name/version/description）
├── customize.sh               安装时执行：检查 APK、设 priv-app 权限
├── post-fs-data.sh            开机早期：修正 priv-app 目录权限
├── service.sh                 开机后：Doze 白名单、精确闹钟、免打扰、沉浸式
└── system/
    ├── priv-app/CareMate/     放 CareMate.apk（需自行复制）
    └── etc/permissions/       privapp-permissions-*.xml 权限白名单
```

## 打包与安装

```bash
copy ..\app\CareMate-release.apk system\priv-app\CareMate\CareMate.apk
cd magisk-module && 7z a ..\CareMate-Kiosk-v1.zip *
# Magisk App → 模块 → 从本地安装 → 重启
```

## 回滚（为什么用模块而不是直接改系统）

```bash
su -c 'touch /data/adb/modules/caremate_kiosk/disable'   # 禁用后重启即恢复
```

整模块禁用 = 一次性撤销 priv-app、白名单与开机脚本，不需要重刷系统。

## 状态

**未在真机安装验证。** `privapp-permissions` 的权限名与 targetSdk 有关，装完请跑
`scripts/50-verify-system.sh`。