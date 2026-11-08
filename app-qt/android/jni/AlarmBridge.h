// 作用：Android 精确闹钟桥的 C++ 接口（schedule/cancel/canScheduleExactAlarms）
// ------------------------------------------------------------------
// JNI 桥：把"精确闹钟 + 通知渠道"从 C++ 调进 Android 系统
// 这是报告 §3.2 B4 说的"必须写 30–60 行 Java"的那部分。
// 当前是骨架：方法签名与调用点齐全，Java 实现见 android/src/com/caremate/app/AlarmBridge.java
// ------------------------------------------------------------------
#pragma once

#include <QObject>
#include <QString>
#include <QDateTime>

class AlarmBridge : public QObject
{
    Q_OBJECT
public:
    explicit AlarmBridge(QObject *parent = nullptr);

    // 在系统层登记一个精确闹钟；失败原因会通过 alarmFailed 发回界面
    Q_INVOKABLE bool schedule(const QString &occurrenceId, const QDateTime &whenLocal,
                              const QString &title, const QString &body);
    Q_INVOKABLE bool cancel(const QString &occurrenceId);
    Q_INVOKABLE bool canScheduleExactAlarms() const;
    // Android 13+ 通知权限；Android 14 起精确闹钟默认拒绝，需要引导或 root 授权
    Q_INVOKABLE void requestPermissions();

signals:
    void alarmFired(const QString &occurrenceId);
    void alarmFailed(const QString &occurrenceId, const QString &reason);

private:
    void ensureChannel();
};
