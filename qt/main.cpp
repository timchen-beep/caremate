// 作用：Qt 入口：注册 ReminderModel、加载 main.qml（Android 走 Qt for Android）
#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickStyle>

#include "core/ReminderModel.h"
#include "net/SyncPuller.h"

int main(int argc, char *argv[])
{
    QGuiApplication app(argc, argv);
    app.setApplicationName(QStringLiteral("CareMate"));
    app.setOrganizationName(QStringLiteral("CareMate"));

    // 老人端用 Material 基础控件即可，不做主题系统（文档要求"不做复杂 UI"）
    QQuickStyle::setStyle(QStringLiteral("Material"));

    ReminderModel model;
    model.loadDemo();          // 先给一屏演示数据，联网后会被服务端覆盖

    // 与云端对接：拉 /v1/plans 与 /v1/state；设 CAREMATE_OFFLINE=1 可只看离线演示
    SyncPuller sync(&model);
    if (!qEnvironmentVariableIsSet("CAREMATE_OFFLINE"))
        sync.start();

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

