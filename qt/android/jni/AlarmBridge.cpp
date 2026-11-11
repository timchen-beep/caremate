// 作用：用 QJniObject 调 Java 侧的闹钟与通知渠道，桌面构建时打印模拟
#include "AlarmBridge.h"

#include <QDebug>
#include <QJniObject>
#include <QCoreApplication>

// 说明：这里用 Qt 6 的 QJniObject 直接调 Java 方法，不必自己写 JNIEXPORT。
// Java 侧仅有三个静态方法（见 src/com/caremate/app/AlarmBridge.java）：
//   schedule(ctx, id, triggerAtMillis, title, body)
//   cancel(ctx, id)
//   canScheduleExact(ctx)
// 全部是 AlarmManager.setExactAndAllowWhileIdle + NotificationManager 的薄封装。

AlarmBridge::AlarmBridge(QObject *parent) : QObject(parent)
{
    ensureChannel();
}

static QJniObject context()
{
    return QNativeInterface::QAndroidApplication::context();
}

void AlarmBridge::ensureChannel()
{
#if defined(Q_OS_ANDROID)
    QJniObject::callStaticMethod<void>(
        "com/caremate/app/AlarmBridge", "ensureChannel",
        "(Landroid/content/Context;)V",
        context().object<jobject>());
#else
    qInfo() << "[AlarmBridge] 非 Android 平台，跳过通知渠道创建";
#endif
}

bool AlarmBridge::canScheduleExactAlarms() const
{
#if defined(Q_OS_ANDROID)
    return QJniObject::callStaticMethod<jboolean>(
        "com/caremate/app/AlarmBridge", "canScheduleExact",
        "(Landroid/content/Context;)Z", context().object<jobject>());
#else
    return false;
#endif
}

bool AlarmBridge::schedule(const QString &occurrenceId, const QDateTime &whenLocal,
                           const QString &title, const QString &body)
{
#if defined(Q_OS_ANDROID)
    if (!canScheduleExactAlarms()) {
        emit alarmFailed(occurrenceId, QStringLiteral("系统未授予精确闹钟权限（Android 14 默认拒绝）"));
        return false;
    }
    const jlong triggerAt = whenLocal.toMSecsSinceEpoch();
    QJniObject::callStaticMethod<void>(
        "com/caremate/app/AlarmBridge", "schedule",
        "(Landroid/content/Context;Ljava/lang/String;JLjava/lang/String;Ljava/lang/String;)V",
        context().object<jobject>(),
        QJniObject::fromString(occurrenceId).object<jstring>(),
        triggerAt,
        QJniObject::fromString(title).object<jstring>(),
        QJniObject::fromString(body).object<jstring>());
    return true;
#else
    qInfo() << "[AlarmBridge] 桌面模拟：登记" << occurrenceId << whenLocal << title;
    return true;
#endif
}

bool AlarmBridge::cancel(const QString &occurrenceId)
{
#if defined(Q_OS_ANDROID)
    QJniObject::callStaticMethod<void>(
        "com/caremate/app/AlarmBridge", "cancel",
        "(Landroid/content/Context;Ljava/lang/String;)V",
        context().object<jobject>(),
        QJniObject::fromString(occurrenceId).object<jstring>());
    return true;
#else
    qInfo() << "[AlarmBridge] 桌面模拟：取消" << occurrenceId;
    return true;
#endif
}

void AlarmBridge::requestPermissions()
{
#if defined(Q_OS_ANDROID)
    QJniObject::callStaticMethod<void>(
        "com/caremate/app/AlarmBridge", "requestPermissions",
        "(Landroid/app/Activity;)V",
        QNativeInterface::QAndroidApplication::context().object<jobject>());
#else
    qInfo() << "[AlarmBridge] 桌面无权限概念";
#endif
}

