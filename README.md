<!-- 作用：本包说明：定位、状态、上手顺序、已知限制 -->
# v3-flash-core · 刷机/系统级改造的核心代码

`v3-flash` 分支里**可执行**的那部分：系统改造脚本、Magisk 定制层、刷机与回滚，以及这套线共用的云端服务。

## 核心文件速览

| 文件 | 作用 |
|---|---|
| `scripts/10-privapp-install.sh` | 把 APK 装成系统特权应用（`/system/priv-app`） |
| `scripts/20-kiosk-on.sh` | 桌面替换 + 状态栏隐藏 + 屏幕常亮 |
| `scripts/30-kiosk-off.sh` | **一键恢复**（演示前必须先演一遍） |
| `scripts/40-chaos.sh` | 断网 / 重启 / 改时间 / 连点 四种异常复现 |
| `scripts/50-verify-system.sh` | 8 项自检：priv-app、精确闹钟、通知、Doze、桌面、状态栏、进程、AlarmManager |
| `magisk-module/` | 可整模块禁用的定制层 + `privapp-permissions` 权限白名单 |
| `device/flash-lineage.sh` | 解锁 → 备份 → 刷官方 LineageOS |
| `device/rollback.sh` | 恢复成普通手机 |
| `legacy-web/server.py` | 云端业务（同 v1 的状态机） |

## 使用顺序

```bash
bash scripts/10-privapp-install.sh
bash scripts/20-kiosk-on.sh
bash scripts/30-kiosk-off.sh        # 先确认能恢复，再上演示
bash scripts/50-verify-system.sh    # 8 项全 OK 才可以演
```

## 状态（重要）

**未在任何真机执行过。** 命令依照 `dumpsys / am / cmd / settings` 的官方用法编写；`20-kiosk-on.sh` 里"设为默认桌面"在不同 ROM 上包名不同，第一次很可能失败，届时手动去「设置 → 默认应用 → 主屏幕」选一次。

## 与完整分支的关系

完整版（含 APK、文档、说明）在 `v3-flash` 分支。

