<!-- 作用：Manifest 补丁说明：加 HOME（默认桌面）与通知策略权限 -->
# AndroidManifest 补丁（刷机/Launcher 方向）

现有 `caremate_app/android/app/src/main/AndroidManifest.xml` 需要加两处；**只在做"唯一桌面"时才加 HOME**。

## 1）允许通知策略（免打扰穿透的必要条件）

```xml
<uses-permission android:name="android.permission.ACCESS_NOTIFICATION_POLICY"/>
```

## 2）设为 HOME（做默认桌面时）

在 `<activity ...>` 里追加一个 intent-filter：

```xml
<intent-filter>
    <action android:name="android.intent.action.MAIN"/>
    <category android:name="android.intent.category.HOME"/>
    <category android:name="android.intent.category.DEFAULT"/>
</intent-filter>
```

## 改完重新打包

```bat
flutter build apk --release
```

签名不变（`CN=CareMate`），可以直接覆盖安装（`adb install -r`）。

## 注意

- 加 HOME 之后，**必须先准备好 `30-kiosk-off.sh`**，否则按 Home 也回不到原桌面。
- 不建议把 App 做成"独占桌面且禁卸载"，评委常要求当场恢复。