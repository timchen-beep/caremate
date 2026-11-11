// 作用：Qt 端同步器：拉 /v1/plans 与 /v1/state 灌进 ReminderModel，把本地动作队列推给 /v1/events
#pragma once

#include <QJsonObject>
#include <QObject>
#include <QTimer>

class HttpClient;
class ReminderModel;

/// 老人端同步器（对应 docs/端上对接_颐伴手机端.md 的拉取/上传节奏）。
///
/// - 启动：`GET /v1/plans?since=0` → `GET /v1/state?since=<cursor>`
/// - 每 15 秒：有待传事件先 `POST /v1/events`，否则拉状态
/// - 动作：模型入队的 confirm/snooze/miss 逐条上传，回执里的 server_seq 写回本地
/// - 呼救：`POST /v1/alarm`（`source=manual`，`occurrence_id` 可空）
class SyncPuller : public QObject
{
    Q_OBJECT

public:
    explicit SyncPuller(ReminderModel *model, QObject *parent = nullptr);

    void start();
    QString state() const { return m_state; }

signals:
    void stateChanged(const QString &state);
    void notice(const QString &text);

private slots:
    void onReplied(const QString &tag, int status, const QJsonObject &body);
    void onFailed(const QString &tag, const QString &reason);
    void tick();

private:
    void setState(const QString &state);
    void pullPlans();
    void pullState();
    void pushEvents();
    void sendSos();

    ReminderModel *m_model = nullptr;
    HttpClient *m_http = nullptr;
    QString m_state = QStringLiteral("offline");
    qint64 m_cursor = 0;
    bool m_busy = false;
    QTimer m_timer;
};
