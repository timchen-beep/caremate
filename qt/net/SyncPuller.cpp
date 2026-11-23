// 作用：Qt 端同步实现：串行请求、增量游标、事件批量上行、呼救上报与离线退避
#include "SyncPuller.h"

#include "HttpClient.h"

#include "core/ReminderModel.h"

#include <QJsonArray>
#include <QtGlobal>

SyncPuller::SyncPuller(ReminderModel *model, QObject *parent)
    : QObject(parent)
    , m_model(model)
    , m_http(new HttpClient(this))
{
    connect(m_http, &HttpClient::replied, this, &SyncPuller::onReplied);
    connect(m_http, &HttpClient::failed, this, &SyncPuller::onFailed);
    connect(m_model, &ReminderModel::sosTriggered, this, &SyncPuller::sendSos);
    connect(m_model, &ReminderModel::eventQueued, this, [this] {
        if (!m_busy)
            pushEvents();
    });

    m_timer.setInterval(15000);
    connect(&m_timer, &QTimer::timeout, this, &SyncPuller::tick);
}

void SyncPuller::start()
{
    m_timer.start();
    pullPlans();
}

void SyncPuller::setState(const QString &state)
{
    if (m_state == state)
        return;
    m_state = state;
    m_model->setSyncState(state);
    emit stateChanged(state);
}

void SyncPuller::pullPlans()
{
    if (m_busy)
        return;
    m_busy = true;
    setState(QStringLiteral("syncing"));
    QUrlQuery query;
    query.addQueryItem(QStringLiteral("since"), QStringLiteral("0"));
    m_http->get(QStringLiteral("plans"), QStringLiteral("/v1/plans"), query);
}

void SyncPuller::pullState()
{
    if (m_busy)
        return;
    m_busy = true;
    setState(QStringLiteral("syncing"));
    QUrlQuery query;
    query.addQueryItem(QStringLiteral("since"), QString::number(m_cursor));
    m_http->get(QStringLiteral("state"), QStringLiteral("/v1/state"), query);
}

void SyncPuller::pushEvents()
{
    if (m_busy)
        return;
    const QVariantList pending = m_model->pendingEvents();
    if (pending.isEmpty()) {
        pullState();
        return;
    }
    QJsonArray items;
    for (const QVariant &entry : pending) {
        const QVariantMap event = entry.toMap();
        QJsonObject item;
        item[QStringLiteral("event_id")] = event.value(QStringLiteral("eventId")).toString();
        item[QStringLiteral("occurrence_id")] =
            event.value(QStringLiteral("occurrenceId")).toString().toLongLong();
        item[QStringLiteral("action")] = event.value(QStringLiteral("action")).toString();
        item[QStringLiteral("ts")] = event.value(QStringLiteral("ts")).toLongLong();
        item[QStringLiteral("device_id")] = QStringLiteral("qt-caremate");
        item[QStringLiteral("reason")] = event.value(QStringLiteral("reason")).toString();
        items.append(item);
    }
    QJsonObject body;
    body[QStringLiteral("events")] = items;

    m_busy = true;
    setState(QStringLiteral("syncing"));
    m_http->post(QStringLiteral("events"), QStringLiteral("/v1/events"), body);
}

void SyncPuller::sendSos()
{
    if (m_busy) {
        // 呼救不能静默丢弃：排队，等这一轮同步结束立刻发（原来直接 return 就没了）
        m_sosPending = true;
        emit notice(QStringLiteral("呼救已排队，正在补发"));
        return;
    }
    m_sosPending = false;
    QJsonObject body;
    body[QStringLiteral("occurrence_id")] = QJsonValue::Null;
    body[QStringLiteral("source")] = QStringLiteral("manual");
    body[QStringLiteral("level")] = 3;
    body[QStringLiteral("ts")] = QDateTime::currentMSecsSinceEpoch();
    body[QStringLiteral("device_id")] = QStringLiteral("qt-caremate");
    body[QStringLiteral("reason")] = QStringLiteral("长按呼救");
    m_busy = true;
    setState(QStringLiteral("syncing"));
    m_http->post(QStringLiteral("alarm"), QStringLiteral("/v1/alarm"), body);
}

void SyncPuller::tick()
{
    if (m_busy)
        return;
    if (m_sosPending) {
        sendSos();          // 上一轮同步期间排队的呼救，优先补发
        return;
    }
    if (!m_model->pendingEvents().isEmpty())
        pushEvents();
    else
        pullState();
}

void SyncPuller::onFailed(const QString &tag, const QString &reason)
{
    Q_UNUSED(tag)
    m_busy = false;
    setState(QStringLiteral("offline"));
    emit notice(QStringLiteral("离线：%1").arg(reason));
    if (m_sosPending)
        sendSos();
}

void SyncPuller::onReplied(const QString &tag, int status, const QJsonObject &body)
{
    m_busy = false;
    if (status == 401 || status == 403) {
        setState(QStringLiteral("error"));
        emit notice(QStringLiteral("令牌失效：请先配对（POST /v1/pair）"));
        return;
    }
    if (status >= 400) {
        setState(QStringLiteral("error"));
        return;
    }

    if (tag == QLatin1String("plans")) {
        QVariantList plans;
        const QJsonArray array = body.value(QStringLiteral("plans")).toArray();
        for (const QJsonValue &value : array)
            plans.append(value.toObject().toVariantMap());
        m_model->applyRemotePlans(plans);
        pullState();
    } else if (tag == QLatin1String("state")) {
        QVariantList occurrences;
        const QJsonArray array = body.value(QStringLiteral("occurrences")).toArray();
        for (const QJsonValue &value : array)
            occurrences.append(value.toObject().toVariantMap());
        m_model->applyRemoteOccurrences(occurrences);
        const qint64 nextSeq = static_cast<qint64>(body.value(QStringLiteral("next_seq")).toDouble());
        if (nextSeq > m_cursor)
            m_cursor = nextSeq;
        setState(QStringLiteral("idle"));
    } else if (tag == QLatin1String("events")) {
        const QJsonArray accepted = body.value(QStringLiteral("accepted")).toArray();
        QVariantList acks;
        for (const QJsonValue &value : accepted) {
            const QJsonObject item = value.toObject();
            // applied=false 表示"这条之前就写过了"（去重命中），server_seq 照样有效：
            // 之前这里 continue 掉了，去重的事件永远拿不到回执，队列永远清不空。
            const qint64 seq = static_cast<qint64>(item.value(QStringLiteral("server_seq")).toDouble());
            if (seq <= 0)
                continue;
            QVariantMap ack;
            ack[QStringLiteral("eventId")] = item.value(QStringLiteral("event_id")).toString();
            ack[QStringLiteral("serverSeq")] = seq;
            acks.append(ack);
        }
        if (!acks.isEmpty())
            m_model->markEventsSent(acks);
        // 被服务端拒收的事件：retryable=false 的是终态（状态冲突/参数不认），必须就地丢弃，
        // 否则整条队列永远重发同一批、每次都失败（这就是"同步状态老是 error"的由来）。
        // retryable=true 的是服务端在忙（锁等待超时），保留在队列里让下一轮重试。
        bool retryLater = false;
        QVariantList failed;
        const QJsonArray rejected = body.value(QStringLiteral("rejected")).toArray();
        for (const QJsonValue &value : rejected) {
            const QJsonObject item = value.toObject();
            if (item.value(QStringLiteral("retryable")).toBool(false)) {
                retryLater = true;
                continue;
            }
            QVariantMap bad;
            bad[QStringLiteral("eventId")] = item.value(QStringLiteral("event_id")).toString();
            bad[QStringLiteral("detail")] = item.value(QStringLiteral("detail")).toString();
            failed.append(bad);
        }
        if (!failed.isEmpty())
            m_model->markEventsFailed(failed);
        setState(retryLater ? QStringLiteral("error") : QStringLiteral("idle"));
    } else if (tag == QLatin1String("alarm")) {
        setState(QStringLiteral("idle"));
        emit notice(QStringLiteral("已通知家人"));
    }
}
