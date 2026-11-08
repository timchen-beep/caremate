// 作用：Qt 入口：注册 ReminderModel、加载 main.qml（Android 走 Qt for Android）
#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickStyle>

#include "core/ReminderModel.h"

int main(int argc, char *argv[])
{
    QGuiApplication app(argc, argv);
    app.setApplicationName(QStringLiteral("CareMate"));
    app.setOrganizationName(QStringLiteral("CareMate"));

    // 老人端用 Material 基础控件即可，不做主题系统（文档要求"不做复杂 UI"）
    QQuickStyle::setStyle(QStringLiteral("Material"));

    ReminderModel model;
    model.loadDemo();          // 首次启动写入演示计划；正式版改为从 MQTT/HTTP 拉取

    QQmlApplicationEngine engine;
    engine.rootContext()->setContextProperty(QStringLiteral("caremate"), &model);
    engine.rootContext()->setContextProperty(QStringLiteral("isAndroid"),
#if defined(Q_OS_ANDROID)
                                             true
#else
                                             false
#endif
    );

    const QUrl url(QStringLiteral("qrc:/CareMate/main.qml"));
    QObject::connect(&engine, &QQmlApplicationEngine::objectCreated, &app,
                     [url](QObject *obj, const QUrl &objUrl) {
                         if (!obj && url == objUrl)
                             QCoreApplication::exit(-1);
                     },
                     Qt::QueuedConnection);
    engine.load(url);

    return app.exec();
}
