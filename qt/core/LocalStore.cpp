// 作用：Qt 端本地库实现：建表、快照读写、游标存取（SQLite / WAL）
#include "LocalStore.h"

#include <QDir>
#include <QJsonDocument>
#include <QJsonObject>
#include <QSqlDatabase>
#include <QSqlError>
#include <QSqlQuery>
#include <QStandardPaths>

namespace {
const char *kConn = "caremate_local_qt";

QString dump(const QVariantMap &map)
{
    return QString::fromUtf8(
        QJsonDocument(QJsonObject::fromVariantMap(map)).toJson(QJsonDocument::Compact));
}

QVariantMap parse(const QString &text)
{
    const QJsonDocument doc = QJsonDocument::fromJson(text.toUtf8());
    return doc.isObject() ? doc.object().toVariantMap() : QVariantMap();
}
} // namespace

LocalStore::LocalStore(QObject *parent)
    : QObject(parent)
{
}

bool LocalStore::open(QString *error)
{
    QString dir = QStandardPaths::writableLocation(QStandardPaths::AppDataLocation);
    if (dir.isEmpty())
        dir = QStringLiteral(".");
    QDir().mkpath(dir);
    m_path = dir + QStringLiteral("/caremate-qt.db");

    QSqlDatabase db = QSqlDatabase::contains(QString::fromLatin1(kConn))
                          ? QSqlDatabase::database(QString::fromLatin1(kConn))
                          : QSqlDatabase::addDatabase(QStringLiteral("QSQLITE"), QString::fromLatin1(kConn));
    db.setDatabaseName(m_path);
    if (!db.open()) {
        if (error)
            *error = db.lastError().text();
        m_open = false;
        return false;
    }
    QSqlQuery pragma(db);
    pragma.exec(QStringLiteral("PRAGMA journal_mode=WAL"));
    m_open = ensureSchema();
    return m_open;
}

bool LocalStore::ensureSchema()
{
    QSqlDatabase db = QSqlDatabase::database(QString::fromLatin1(kConn));
    QSqlQuery query(db);
    const QStringList ddl = {
        QStringLiteral("CREATE TABLE IF NOT EXISTS plans(id TEXT PRIMARY KEY, json TEXT NOT NULL)"),
        QStringLiteral("CREATE TABLE IF NOT EXISTS occurrences(id TEXT PRIMARY KEY, json TEXT NOT NULL)"),
        QStringLiteral("CREATE TABLE IF NOT EXISTS events(event_id TEXT PRIMARY KEY, json TEXT NOT NULL,"
                       " server_seq INTEGER NOT NULL DEFAULT 0)"),
        QStringLiteral("CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT NOT NULL)"),
    };
    for (const QString &sql : ddl) {
        if (!query.exec(sql))
            return false;
    }
    return true;
}

bool LocalStore::load(QVariantList *rules, QVariantList *occurrences, QVariantList *events, qint64 *cursor)
{
    if (!m_open)
        return false;
    QSqlDatabase db = QSqlDatabase::database(QString::fromLatin1(kConn));

    auto readAll = [&db](const QString &table) {
        QVariantList out;
        QSqlQuery query(db);
        if (!query.exec(QStringLiteral("SELECT json FROM %1").arg(table)))
            return out;
        while (query.next())
            out.append(parse(query.value(0).toString()));
        return out;
    };

    if (rules)
        *rules = readAll(QStringLiteral("plans"));
    if (occurrences)
        *occurrences = readAll(QStringLiteral("occurrences"));
    if (events)
        *events = readAll(QStringLiteral("events"));
    if (cursor)
        *cursor = this->cursor();
    return rules && !rules->isEmpty();
}

bool LocalStore::save(const QVariantList &rules, const QVariantList &occurrences, const QVariantList &events)
{
    if (!m_open)
        return false;
    QSqlDatabase db = QSqlDatabase::database(QString::fromLatin1(kConn));

    db.transaction();
    bool ok = true;
    auto rewrite = [&db, &ok](const QString &table, const QVariantList &list, const QString &key) {
        QSqlQuery del(db);
        if (!del.exec(QStringLiteral("DELETE FROM %1").arg(table))) {
            ok = false;
            return;
        }
        QSqlQuery ins(db);
        ins.prepare(QStringLiteral("INSERT OR REPLACE INTO %1(%2, json) VALUES (?, ?)").arg(table, key));
        for (const QVariant &entry : list) {
            const QVariantMap map = entry.toMap();
            ins.addBindValue(map.value(key).toString());
            ins.addBindValue(dump(map));
            if (!ins.exec()) {
                ok = false;
                return;
            }
        }
    };

    rewrite(QStringLiteral("plans"), rules, QStringLiteral("id"));
    rewrite(QStringLiteral("occurrences"), occurrences, QStringLiteral("id"));
    if (ok) {
        QSqlQuery del(db);
        del.exec(QStringLiteral("DELETE FROM events"));
        QSqlQuery ins(db);
        ins.prepare(QStringLiteral("INSERT OR REPLACE INTO events(event_id, json, server_seq)"
                                  " VALUES (?, ?, ?)"));
        for (const QVariant &entry : events) {
            const QVariantMap map = entry.toMap();
            ins.addBindValue(map.value(QStringLiteral("eventId")).toString());
            ins.addBindValue(dump(map));
            ins.addBindValue(map.value(QStringLiteral("serverSeq")).toLongLong());
            if (!ins.exec()) {
                ok = false;
                break;
            }
        }
    }
    ok ? db.commit() : db.rollback();
    return ok;
}

qint64 LocalStore::cursor() const
{
    if (!m_open)
        return 0;
    QSqlDatabase db = QSqlDatabase::database(QString::fromLatin1(kConn));
    QSqlQuery query(db);
    query.prepare(QStringLiteral("SELECT v FROM meta WHERE k='server_seq'"));
    if (!query.exec() || !query.next())
        return 0;
    return query.value(0).toLongLong();
}

void LocalStore::setCursor(qint64 value)
{
    if (!m_open)
        return;
    QSqlDatabase db = QSqlDatabase::database(QString::fromLatin1(kConn));
    QSqlQuery query(db);
    query.prepare(QStringLiteral("INSERT OR REPLACE INTO meta(k, v) VALUES ('server_seq', ?)"));
    query.addBindValue(QString::number(value));
    query.exec();
}
