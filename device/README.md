<!-- 作用：刷机方向的说明：选什么机型、怎么刷、怎么回滚、风险在哪 -->
# 刷机与回滚

把一台**专用演示机**刷成 LineageOS，以获得系统级 kiosk 与更干净的省电策略。
**不要用日常手机。**

## 文件

| 文件 | 作用 |
|---|---|
| `机型对照.md` | 哪些机型有官方 LineageOS、解锁难度、坑（如小米等 7 天） |
| `flash-lineage.sh` | 预检机型 → 备份 boot/dtbo/vbmeta → 解锁 → 刷官方包 |
| `rollback.sh` | 解除 kiosk、禁用 Magisk 模块、按需卸载 App、重启验证 |

## 用法

```bash
bash flash-lineage.sh sunfish            # 以 Pixel 4a 为例
# 刷完先回归基线：电话、相机、WiFi、指纹
bash rollback.sh                         # 演一遍恢复
```

## 风险（务必先读）

- 刷机**会清空数据**，且可能变砖；先备份原厂分区。
- 部分机型（小米）解锁要等 7 天，赶工期别选。
- 刷完先跑 `scripts/50-verify-system.sh`，再上演示。

## 状态

**未在任何真机执行过。**