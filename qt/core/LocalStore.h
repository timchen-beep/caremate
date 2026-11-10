// 作用：Qt 端本地库（SQLite 四表 + 游标）：规则/实例/记录/事件与 server_seq 落盘，冷启动不丢
#pragma once

#include <QObject>
#include <QString>
#include <QVariantList>

/// 本地主副本（QtSql / SQLite）。
///
/// Flutter 验证版用的是 sqflite 三表；这里用同一套语义落到 QtSql：
///   rules(plan) / occurrences / records / events(event_id PK, server_seq) / meta(k,v)
///
/// 落盘策略：AppCore/ReminderModel 变更后 1 秒防抖写一次整表快照（单事务），
/// 不做增量——本项目的量级（一天 ≤ 20 条实例）用快照足够，换来实现简单、不会出现半写。
class LocalStore : public QObject
{
    Q_OBJECT

public:
    explicit LocalStore(QObject *parent = nullptr);

    bool open(QString *error = nullptr);

    /// 读全部快照；库里没有数据返回 false（首次启动）。
    bool load(QVariantList *rules, QVariantList *occurrences, QVariantList *events, qint64 *cursor);

    /// 覆盖写全部快照（单事务）。
    bool save(const QVariantList &rules, const QVariantList &occurrences, const QVariantList &events);

    qint64 cursor() const;
    void setCursor(qint64 value);

    bool isOpen() const { return m_open; }
    QString path() const { return m_path; }

private:
    bool ensureSchema();

    QString m_path;
    bool m_open = false;
};
