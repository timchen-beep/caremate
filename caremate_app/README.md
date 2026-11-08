<!-- 作用：本包说明：定位、状态、上手顺序、已知限制 -->
# CareMate App（Flutter）—— 老人口袋里的那一端

形态分工：**老人端就是 App**（系统通知、锁屏亮屏、离线记录），**看护端是 Web 看板**（`../caremate-cloud/web/dashboard.html`）。

老人端界面的定量标准（对照《需求扩展与技术路线》R7-6，全部写在 `lib/screens/today.dart` 顶部常量里）：

| 指标 | 要求 | 实现 |
|---|---|---|
| 正文 | ≥24pt | `kBody = 24`，主题 `bodyMedium: 24` |
| 提醒标题 | 尽量大 | `kTitle = 42` |
| 主按钮 | ≥48×48 | `kTap = 84` 高、整行宽、3px 描边 |
| 对比 | ≥7:1 | 正文 `#14264A` on `#FFFFFF` ≈ 13:1 |
| 单屏选项 | ≤4 | 提醒卡只有 3 个按钮 |
| 完成一件事 | ≤3 步 | 点开 → 点「吃了，记一下」 |

终端 App：负责**到点提醒、一键确认、离线记录**；云端与 Web 看板在 `../caremate-cloud`。

## 1. 目录

```
caremate_app/
├─ pubspec.yaml            依赖
├─ lib/main.dart           入口、底部导航、前后台切换
├─ lib/state.dart          本地状态与同步（先落本地，再上行）
├─ lib/models.dart         Plan / AppEvent / DueItem
├─ lib/api.dart            云端接口（bundle / events）
├─ lib/notify.dart         本地通知（核心：断网也响）
└─ lib/screens/
   ├─ today.dart           今天：待办卡片 + 三个大按钮 + 今日记录
   ├─ records.dart         记录：近 7 天统计 + 流水
   └─ settings.dart        我的：服务器、令牌、绑定码、测试通知
```

## 2. 跑起来

```bash
# 1) 生成平台工程（只生成一次）
flutter create caremate_app --project-name caremate --platforms android,ios

# 2) 用本目录的 lib/ 与 pubspec.yaml 覆盖生成出来的同名内容
#    然后
cd caremate_app
flutter pub get

# 3) 先启动云端（另一个终端）
cd ../caremate-cloud
python server.py --port 8000

# 4) 运行 App（Android 模拟器）
flutter run --dart-define=API_BASE=http://10.0.2.2:8000 --dart-define=API_TOKEN=app-elder-001
```

真机调试：手机与电脑同一 WiFi，`API_BASE` 换成电脑的局域网 IP（如 `http://192.168.1.10:8000`），并放行 Windows 防火墙的 8000 端口。
iOS 模拟器可用 `http://127.0.0.1:8000`。

## 3. Android 必须补的三处配置

**① `android/app/src/main/AndroidManifest.xml`**（`<manifest>` 内、`<application>` 外）

```xml
<uses-permission android:name="android.permission.INTERNET"/>
<uses-permission android:name="android.permission.POST_NOTIFICATIONS"/>
<uses-permission android:name="android.permission.SCHEDULE_EXACT_ALARM"/>
<uses-permission android:name="android.permission.USE_EXACT_ALARM"/>
<uses-permission android:name="android.permission.RECEIVE_BOOT_COMPLETED"/>
<uses-permission android:name="android.permission.VIBRATE"/>
<uses-permission android:name="android.permission.WAKE_LOCK"/>
```

`<application>` 内加两个接收器（重启后恢复定时）：

```xml
<receiver android:exported="false"
    android:name="com.dexterous.flutterlocalnotifications.ScheduledNotificationReceiver" />
<receiver android:exported="false"
    android:name="com.dexterous.flutterlocalnotifications.ScheduledNotificationBootReceiver">
  <intent-filter>
    <action android:name="android.intent.action.BOOT_COMPLETED"/>
    <action android:name="android.intent.action.MY_PACKAGE_REPLACED"/>
    <action android:name="android.intent.action.QUICKBOOT_POWERON"/>
    <action android:name="com.htc.intent.action.QUICKBOOT_POWERON"/>
  </intent-filter>
</receiver>
```

**② `android/app/build.gradle`**：`flutter_local_notifications` 需要 Java 8+ 的 desugaring

```gradle
android {
    compileOptions {
        coreLibraryDesugaringEnabled true
        sourceCompatibility JavaVersion.VERSION_1_8
        targetCompatibility JavaVersion.VERSION_1_8
    }
}
dependencies {
    coreLibraryDesugaring 'com.android.tools:desugar_jdk_libs:2.0.4'
}
```

**③ iOS（仅开发期）**：`android/app/src/main/AndroidManifest.xml` 允许明文 HTTP

```xml
<key>NSAppTransportSecurity</key>
<dict><key>NSAllowsArbitraryLoads</key><true/></dict>
```

## 4. 交互流程

1. App 启动 → 读本地计划（没有则写入 3 条示例）→ 按计划重建每日定时通知。
2. 到点：系统通知（精确闹钟，`exactAllowWhileIdle`）→ 点开进入「今天」。
3. 点「已服药 / 已完成」→ 本地立刻写入终态 → 尝试 `POST /api/v1/events`（幂等）→ 失败留在本地，联网后自动补传。
4. 家属在 Web 看板看到同一条记录；正在改的计划下次 `bundle` 拉取时会覆盖本地。

## 5. 状态机

`计划时刻 → 待提示 → 已提示 → {已确认 | 稍后 | 未确认}`

- 三十分钟内没响应，Web 端仍会显示"未确认"（App 在下次启动时补写 `missed`）。
- 事件 ID = `userId:planId:YYYYMMDD:HHmm`，重复提交云端只收第一条。

## 6. 未在本机编译验证（重要）

本机没有 Flutter SDK，**这套代码没有实际 `flutter run` 过**。以下三处若 `pub get` 解析到不同大版本，可能需要按官方 API 微调：

| 位置 | 可能的变化 |
|---|---|
| `notify.dart` 的 `zonedSchedule(...)` | 17.x 用 `androidScheduleMode:`；若解析到 16.x，需去掉该参数并加 `uiLocalNotificationDateInterpretation: UILocalNotificationDateInterpretation.absoluteTime` |
| `notify.dart` 的权限请求 | 17.x 为 `requestNotificationsPermission()` / `requestExactAlarmsPermission()`；旧版为 `requestPermission()` |
| `today.dart` 的 `MaterialStatePropertyAll` | Flutter 3.22+ 已改名 `WidgetStatePropertyAll`（旧名仍可用，只有弃用警告） |

云端与 Web 看板是**实测跑通**的（见 `../caremate-cloud/README.md`），App 端代码为按 Flutter 3.x 常规写法编写的初版，需要在本机 `flutter run` 一次做编译校验。

## 7. 国产 ROM 的注意点

- 小米/华为/OPPO/vivo：需在系统设置里允许「自启动」「后台运行」，否则进程被杀后只能依赖系统级定时通知。
- Android 12+：首次启动会请求「闹钟和提醒」权限，拒绝后通知可能延后几分钟。
- 省电模式会限制精确闹钟，演示前建议关闭省电优化。

<!-- 文件：caremate_app/README.md -->
