// 作用：Qt 端唯一 HTTP 出口：/v1/* 的 GET/POST 封装（令牌、地址、JSON 解码都集中在这里）
#pragma once

#include <QHash>
#include <QJsonObject>
#include <QObject>
#include <QUrlQuery>

class QNetworkAccessManager;
class QNetworkReply;

/// 与后端 `/v1/*` 通信的最小客户端。
///
/// 地址与令牌来源（优先级从高到低）：
///   1. 环境变量 `CAREMATE_API` / `CAREMATE_TOKEN`
///   2. QSettings 的 `api/baseUrl`、`api/token`
///   3. 默认 `http://10.0.2.2:8400`（Android 模拟器访问宿主机）/ `app-elder-001`
class HttpClient : public QObject
{
    Q_OBJECT

public:
    explicit HttpClient(QObject *parent = nullptr);

    QString baseUrl() const { return m_baseUrl; }
    QString token() const { return m_token; }
    void setToken(const QString &token);

    /// 发起请求；完成时发 `replied(tag, status, body)` 或 `failed(tag, reason)`。
    void get(const QString &tag, const QString &path, const QUrlQuery &query = QUrlQuery());
    void post(const QString &tag, const QString &path, const QJsonObject &body);

signals:
    void replied(const QString &tag, int status, const QJsonObject &body);
    void failed(const QString &tag, const QString &reason);

private:
    void track(const QString &tag, QNetworkReply *reply);

    QNetworkAccessManager *m_nam = nullptr;
    QString m_baseUrl;
    QString m_token;
    QHash<QNetworkReply *, QString> m_tags;
};
