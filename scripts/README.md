<!-- 作用：Android 系统级改造脚本的说明：每个脚本做什么、按什么顺序执行、怎么回滚 -->
# 系统级改造脚本

这些脚本把一台普通安卓机改成"专注模式"设备（只有这一个 App）。**都需要真机 + adb**，多数需要 root。

## 执行顺序（别跳）

```bash
bash 10-privapp-install.sh    # 1. 装成系统特权应用，免授权拿到精确闹钟
bash 20-kiosk-on.sh           # 2. 设为默认桌面 + 隐藏状态栏 + 屏幕常亮
bash 30-kiosk-off.sh          # 3. 立刻演一遍恢复（演示前必做！）
bash 50-verify-system.sh      # 4. 8 项自检，全 OK 才算改造成功
bash 40-chaos.sh offline      # 5. 四种异常复现：offline / reboot / time-skew / tap-spam
```

## 每个脚本

| 脚本 | 做什么 | 风险 |
|---|---|---|
| `10-privapp-install.sh` | APK 放进 `/system/priv-app`，放权限白名单 | 低；卸载可恢复 |
| `20-kiosk-on.sh` | 设为默认桌面、`policy_control immersive.full=*`、`svc power stayon true` | **中**，会锁住桌面 |
| `30-kiosk-off.sh` | 还原桌面/状态栏/常亮/自动时间 | 救命脚本 |
| `40-chaos.sh` | 断网 60 秒 / 重启 / 拨时间 / 连点 10 次 | 中，会短暂断网 |
| `50-verify-system.sh` | 8 项逐条打勾：priv-app、精确闹钟、通知、Doze、默认桌面、状态栏、进程、AlarmManager | 无 |

## 状态

**未在任何真机执行过。** 命令按 `dumpsys / am / cmd / settings` 官方用法编写；
`20-kiosk-on.sh` 里"设为默认桌面"在不同 ROM 上包名不同，第一次很可能失败，届时手动去
「设置 → 默认应用 → 主屏幕」选一次。