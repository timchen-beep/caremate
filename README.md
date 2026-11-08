<!-- 作用：本包说明：定位、状态、上手顺序、已知限制 -->
# CareMate 刷机方向包

> 方向：**官方 LineageOS 换 ROM + Magisk 定制层，不编译 AOSP。**
> 目标：把老人端变成"只有这一件事"的设备，同时保留一键恢复。

## 状态

| 部分 | 状态 |
|---|---|
| pp/CareMate-release.apk | **已编译、已签名**（23.9 MB，v1+v2，证书 CN=CareMate） |
| magisk-module/ | 模块文件齐（module.prop / customize.sh / service.sh / privapp 权限 xml），**未在真机安装** |
| scripts/ | 5 个脚本齐（priv-app、kiosk on/off、chaos、8 项自检），**未在真机执行** |
| device/ | 选机对照 + 刷机/回滚脚本骨架，**未在真机刷过** |
| legacy-web/ | Python 服务 + 看板 + 七套测试，**已验收 56/56** |

**一句话：脚本和模块是齐的，但没有任何一步在真机上跑过。** 报告里必须这么写。

## 上手顺序

```bat
:: 0) 先确认云端没问题
cd legacy-web
python server.py --host 0.0.0.0 --port 8000
curl http://127.0.0.1:8000/api/v1/health

:: 1) 手机连上（同一网段，改 App 里的服务器地址为电脑局域网 IP）
:: 2) 装 APK
adb install -r app\CareMate-release.apk

:: 3) 先做"不刷机"的半套：priv-app + kiosk
bash scripts/10-privapp-install.sh
bash scripts/20-kiosk-on.sh
bash scripts/30-kiosk-off.sh      :: 立刻演一遍恢复
bash scripts/50-verify-system.sh  :: 8 项自检

:: 4) 真要刷机再走这一步（会清空数据、可能变砖）
bash device/flash-lineage.sh sunfish
bash device/rollback.sh
```

## 目录

```
CareMate_刷机版_<日期>/
├── README.md
├── app/
│   ├── CareMate-release.apk        签名 APK
│   ├── AndroidManifest-补丁.md     加 HOME / ACCESS_NOTIFICATION_POLICY
│   └── 签名与升级说明.md
├── magisk-module/                  可整体禁用的定制层
│   ├── module.prop / customize.sh / service.sh / post-fs-data.sh
│   └── system/{priv-app,etc/permissions}
├── scripts/                        adb + root 运行时脚本
│   ├── 10-privapp-install.sh  20-kiosk-on.sh  30-kiosk-off.sh
│   ├── 40-chaos.sh            50-verify-system.sh（8 项自检）
├── device/                         刷机与回滚
│   ├── flash-lineage.sh / rollback.sh / 机型对照.md
├── docs/
│   ├── FLASH.md（技术方案） / 验收清单.md
└── legacy-web/                     云端 + 看板（已验收）
```

## 已知限制（4 条，与上一份备份同样原则）

1. **未在真机刷机**：device/*.sh 是按 fastboot 官方流程写的骨架，机型不同命令有差异。
2. **Magisk 模块未安装验证**：privapp-permissions xml 的权限名与 targetSdk 有关，装完必须跑 50-verify-system.sh。
3. **kiosk 脚本的桌面恢复**依赖 ROM 自带 Launcher 包名（脚本里列了 4 个候选，可能都不匹配）。
4. **APK 未在真机安装过**（db devices 为空）：锁屏通知、精确闹钟都还是"代码齐、未验证"。

## 安全提醒

- 刷机会清空数据，**只能用专用演示机**
- 20-kiosk-on.sh 执行前必须先准备好 30-kiosk-off.sh
- 演示前 24 小时冻结系统，不再刷/不再改

<!-- 文件：README.md -->

## 分支地图

本分支实际包含：

- `app/`
- `device/`
- `docs/`
- `legacy-web/`
- `magisk-module/`
- `scripts/`

不在本分支的内容，去哪找：

- `caremate_app/` → Flutter 老人端在 `main` 的 `app/`
- `app-qt/` → Qt 骨架在 `main` 的 `qt/`、或 `v2-qt` 的 `app-qt/`
- `qt/` → Qt 骨架在 `v2-qt` / `v2-qt-core` 的 `app-qt/`
- `pi/` → 板子部署在 `main` 的 `pi/`、或 `v2-qt` 的 `pi/`
- `esp32/` → 雷达固件在 `main` 的 `server/firmware/`、或 `v2-qt` 的 `esp32/`
- `server/` → 后端在 `main` 的 `server/`；本分支里叫 `legacy-web/` 或 `caremate-cloud/`
