<!-- 作用：Flutter 端源码的说明：文件分工与数据流 -->
# 老人端源码（Flutter）

## 文件分工

| 文件 | 职责 |
|---|---|
| `main.dart` | App 入口；初始化状态与本地通知；三个 tab |
| `state.dart` | **核心**：拉计划、提交动作、离线队列、补传、同步 |
| `api.dart` | HTTP 封装（Bearer 令牌、JSON、错误码 → 中文提示） |
| `models.dart` | 数据模型：Occurrence / Plan / AppEvent（与契约字段一一对应） |
| `notify.dart` | 本地通知与精确闹钟（断网也照响） |
| `screens/today.dart` | 今天页（到点卡片 + 三个大按钮） |
| `screens/records.dart` | 记录页（统计 + 今日事项 + 动作流水） |
| `screens/settings.dart` | 我的页（服务器地址、令牌、配对码、自检） |

## 一次确认的数据流

```
today.dart 按钮 → state.record() → 落盘队列 → pushPending()
   → POST /api/v1/occurrences/{id}/events → 服务端 transition()
```

断网时动作只进本地队列；联网后按原样重发，服务端靠 `event_id` 去重（不会重复入账）。

## 状态

已能 `flutter build apk` 出签名包；**锁屏通知与精确闹钟未在真机验证**。