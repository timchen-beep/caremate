# 刷机方向（技术方案）

> 一句话：**官方 LineageOS 换 ROM + Magisk 定制层，不编译 AOSP。**
> 把"刷机"降级为"换 ROM + 装模块"，只改运行时配置，不动系统源码。

## 一、为什么这样选

| 选项 | 结论 | 理由 |
|---|---|---|
| 自编 AOSP | ❌ | 编一次 4–8 小时，改一行要重编，课程周期内不可控 |
| 自编 LineageOS | ❌ | 同上，且要处理机型 device tree |
| **官方 LineageOS 包** | ✅ | 官方维护、驱动齐、可直接 priv-app 化 |
| 只 root 不换 ROM | ⚠️ 备选 | 能做 7/8 项，但厂商省电策略可能杀提醒 |
| 不 root 不刷机 | ✅ 兜底 | 只能做 PWA，锁屏提醒做不到 |

## 二、改造清单（8 项）

| # | 目标 | 手段 | 验收 |
|---|---|---|---|
| 1 | 特权权限免授权 | priv-app + `privapp-permissions-com.caremate.caremate.xml` | `scripts/50-verify-system.sh` 第 1/2/3 项 |
| 2 | 唯一桌面 | MainActivity 设为 HOME，或极小 Launcher | 按 Home 回不到原桌面 |
| 3 | 隐藏状态栏/导航栏 | `settings put global policy_control immersive.full=*` | 全屏截图无状态栏 |
| 4 | 开机直接进 App | priv-app + BOOT_COMPLETED（Launcher 方式更彻底） | 重启 60 秒内进界面 |
| 5 | 精确闹钟免授权 | privapp 权限 + `appops set SCHEDULE_EXACT_ALARM allow` | `dumpsys alarm` 有条目 |
| 6 | Doze 不漂移 | `cmd deviceidle whitelist +pkg` | 息屏 8 小时误差 <1 分钟 |
| 7 | 免打扰穿透 | `ACCESS_NOTIFICATION_POLICY` + 呼救渠道 bypassDnd | 开免打扰仍弹呼救 |
| 8 | 一键恢复 | `scripts/30-kiosk-off.sh` + 禁用模块 | 手机变回普通手机 |

## 三、执行顺序（Pixel 机型，3–4 天）

1. **D1 上午**：`device/flash-lineage.sh` → 解锁、备份、刷官方包 → 回归基线（电话/相机/WiFi）
2. **D1 下午**：刷 Magisk → 把 APK 放进模块 `system/priv-app/CareMate/CareMate.apk` → 安装模块 → 重启
3. **D2**：`scripts/20-kiosk-on.sh` → 桌面、状态栏、常亮
4. **D3**：端到端联调（APK ↔ 服务 ↔ 看板）+ `40-chaos.sh` 四种异常
5. **D4**：`30-kiosk-off.sh` 回滚演练 + 录演示视频

## 四、风险与回滚

| 风险 | 应对 |
|---|---|
| 变砖 | 刷前 `fastboot` 备份 boot/dtbo/vbmeta；官方包可回刷 |
| 演示当天锁死退不出 | **先写并演练 `30-kiosk-off.sh`**，再执行 on |
| 厂家 OTA 覆盖 | 关自动更新；演示前 24h 冻结系统 |
| 机型没官方包 | `device/机型对照.md` 三条硬标准，别选冷门机 |

## 五、对 App 的改动（仅 2 处）

1. `AndroidManifest.xml` 增加 `HOME` intent-filter（做 Launcher 时）+ `ACCESS_NOTIFICATION_POLICY`
2. 呼救渠道已 `bypassDnd`（无需改代码）

## 六、报告口径

> 演示机采用 LineageOS 官方 ROM + Magisk 定制层，将老人端预置为系统特权应用并替换桌面，以获得系统级 kiosk 与精确闹钟能力；不涉及 AOSP 源码编译。

## 七、如果时间只够一半

**先做"不换 ROM 的模块化改造"**：priv-app + overlay + 桌面替换，在官方系统上能拿到 7/8 项，风险低一半、2 天能完。
只有一种情况才值得真换 ROM：**官方系统省电策略导致息屏后提醒漂移**（先用 8 小时测试确认）。