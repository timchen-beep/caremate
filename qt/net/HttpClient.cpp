// 作用：Qt 端 HTTP 实现：地址/令牌解析、请求跟踪、JSON 解码与错误分类
#include "HttpClient.h"

#include <QJsonDocument>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QNetworkRequest>
#include <QSettings>
#include <QUrl>

HttpClient::HttpClient(QObject *parent)
    : QObject(parent)
    , m_nam(new QNetworkAccessManager(this))
{
    QSettings settings;
    m_baseUrl = qEnvironmentVariable("CAREMATE_API");
    if (m_baseUrl.isEmpty())
        m_baseUrl = settings.value(QStringLiteral("api/baseUrl")).toString();
    if (m_baseUrl.isEmpty())
        m_baseUrl = QStringLiteral("http://10.0.2.2:8400");
    while (m_baseUrl.endsWith(QLatin1Char('/')))
        m_baseUrl.chop(1);

    m_token = qEnvironmentVariable("CAREMATE_TOKEN");
    if (m_token.isEmpty())
        m_token = settings.value(QStringLiteral("api/token")).toString();
    if (m_token.isEmpty())
        m_token = QStringLiteral("app-elder-001");   // 后端 init_db 写入的演示令牌
}

void HttpClient::setToken(const QString &token)
{
    m_token = token;
    QSettings settings;
    settings.setValue(QStringLiteral("api/token"), token);
}

void HttpClient::get(const QString &tag, const QString &path, const QUrlQuery &query)
{
    QUrl url(m_baseUrl + path);
    if (!query.isEmpty())
        url.setQuery(query);
    QNetworkRequest request(url);
    request.setRawHeader("Accept", "application/json");
    if (!m_token.isEmpty())
        request.setRawHeader("X-Token", m_token.toUtf8());
    track(tag, m_nam->get(request));
}

void HttpClient::post(const QString &tag, const QString &path, const QJsonObject &body)
{
    QNetworkRequest request(QUrl(m_baseUrl + path));
    request.setHeader(QNetworkRequest::ContentTypeHeader, QStringLiteral("application/json"));
    request.setRawHeader("Accept", "application/json");
    if (!m_token.isEmpty())
        request.setRawHeader("X-Token", m_token.toUtf8());
    track(tag, m_nam->post(request, QJsonDocument(body).toJson(QJsonDocument::Compact)));
}

void HttpClient::track(const QString &tag, QNetworkReply *reply)
{
    m_tags.insert(reply, tag);
    connect(reply, &QNetworkReply::finished, this, [this, reply] {
        m_tags.remove(reply);
        reply->deleteLater();
        const int status = reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt();
        const QByteArray payload = reply->readAll();
        if (reply->error() != QNetworkReply::NoError && status == 0) {
            emit failed(tag, reply->errorString());
            return;
        }
        QJsonObject body;
        const QJsonDocument doc = QJsonDocument::fromJson(payload);
        if (doc.isObject())
            body = doc.object();
        emit replied(tag, status, body);
    });
}
