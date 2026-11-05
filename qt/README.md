# Qt 老人端（B4 路线，骨架）

> **状态：骨架，未编译。** 正式交付的老人端是 `../app/`（Flutter，已能出签名 APK）。
> 这份代码是为了对齐课程文档的技术路线（Qt for Android）而保留的可替换实现。

## 为什么留着它

项目的通信契约与数据模型独立于客户端，因此老人端可以平替。这份 QML 代码证明了：

- 同一个契约可以由 Qt 实现（`core/ReminderModel.cpp` 复刻了规则→实例的展开逻辑）
- Android 系统级能力（精确闹钟）在 Qt 下需要一段 Java/JNI 胶水（`android/jni/AlarmBridge.cpp` + `android/src/.../AlarmBridge.java`）

## 结构

```
qt/
├── CMakeLists.txt          Qt 6.5+ / qt_add_qml_module
├── main.cpp                注册 ReminderModel
├── main.qml                三 tab 外壳（今天 / 记录 / 我的）
├── pages/
│   ├── TodayPage.qml       到点卡片 + 确认/稍后/没做
│   ├── RecordPage.qml      喝水/入睡/起床一键记录
│   ├── FamilyPage.qml      家属模式（同一 APK 的另一种界面）
│   └── SosButton.qml       长按 3 秒呼救
├── core/ReminderModel.*    规则→实例，状态机
└── android/                精确闹钟（setExactAndAllowWhileIdle）+ 通知渠道
```

## 编译（需要 Qt 6.5+ 与 Android Kit）

```bash
qt-cmake -S . -B build
cmake --build build
# 桌面版先看布局：./build/appCareMate
# 出 APK：--target apk（需配置 Android Kit）
```

## 已知限制

- 未编译验证：搭建工具链时 `download.qt.io` 与镜像返回的 qtbase 包校验失败。
- `AlarmBridge` 的 JNI 只在真机上有意义，桌面构建走的是打印模拟。
- 视觉细节未做无障碍量测（Flutter 端有：32px 正文 / 84px 按钮 / 14.9:1 对比）。