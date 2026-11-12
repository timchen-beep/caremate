// 作用：Qt 规则模型的实现：七种规则展开、30 秒刷新到期判断（对照后端 slots_on/transition）
#include "ReminderModel.h"

#include "LocalStore.h"

#include <QDebug>
#include <QSet>
#include <QUuid>

ReminderModel::ReminderModel(QObject *parent) : QObject(parent)
{
    // 本地主副本：冷启动读这个库，网络只是同步，不是数据来源（4.1 架构图）
    m_store = new LocalStore(this);
    m_saveTimer.setSingleShot(true);
    m_saveTimer.setInterval(1000);
    connect(&m_saveTimer, &QTimer::timeout, this, &ReminderModel::persistNow);

    // 30 秒刷新一次到期判断：与后端 scheduler 的 30 s 节奏一致
    m_tick.setInterval(30 * 1000);
    connect(&m_tick, &QTimer::timeout, this, &ReminderModel::refresh);
    m_tick.start();

    loadFromStoreOrDemo();   // 有库读库，没有才写演示数据并落盘
}

// 函数 isoLocal：datetime → 'yyyy-MM-dd HH:mm'，实例的唯一时刻身份
QString ReminderModel::isoLocal(const QDateTime &dt)
{
    return dt.toString(QStringLiteral("yyyy-MM-dd HH:mm"));
}

// 函数 loadDemo：写入演示规则（用药/喝水/散步）
void ReminderModel::loadDemo()
{
    m_rules.clear();
    Rule a; a.id = "p-amlodipine"; a.title = "苯磺酸氨氯地平 5mg"; a.kind = "medication";
    a.times = {"08:00", "20:00"}; a.kindRule = "daily"; a.dose = "1 片 · 餐后";
    Rule w; w.id = "p-water"; w.title = "喝水 200ml"; w.kind = "water";
    w.times = {"10:00", "15:30"}; w.kindRule = "daily"; w.dose = "200 ml";
    Rule s; s.id = "p-walk"; s.title = "下楼散步"; s.kind = "activity";
    s.times = {"16:00"}; s.kindRule = "interval"; s.intervalN = 2;
    s.startDate = QDate::currentDate().toString(Qt::ISODate);
    m_rules << a << w << s;
    rebuild();
    emit changed();
}

// 函数 matches：判断某条规则在某天是否生效（每天/每周/间隔/一次）
bool ReminderModel::matches(const Rule &r, const QDate &d) const
{
    if (r.kindRule == "daily") return true;
    if (r.kindRule == "weekly") return r.weekdays.contains(d.dayOfWeek());
    if (r.kindRule == "interval") {
        const QDate start = QDate::fromString(r.startDate, Qt::ISODate);
        if (!start.isValid()) return true;
        return (start.daysTo(d) % qMax(1, r.intervalN)) == 0;
    }
    if (r.kindRule == "once") return r.startDate == d.toString(Qt::ISODate);
    return true;
}

// 函数 rebuild：规则 → 未来三天实例列表
void ReminderModel::rebuild()
{
    m_occs.clear();
    const QDate today = QDate::currentDate();
    for (int offset = 0; offset < 3; ++offset) {
        const QDate d = today.addDays(offset);
        for (const Rule &r : m_rules) {
            if (!matches(r, d)) continue;
            for (const QString &t : r.times) {
                const QStringList hm = t.split(':');
                if (hm.size() != 2) continue;
                QDateTime due(d, QTime(hm[0].toInt(), hm[1].toInt()));
                Occ o;
                o.id = r.id + "@" + isoLocal(due);
                o.planId = r.id;
                o.title = r.title;
                o.slotLocal = isoLocal(due);
                o.due = due;
                o.state = "pending";
                m_occs << o;
            }
        }
    }
    std::sort(m_occs.begin(), m_occs.end(), [](const Occ &a, const Occ &b) {
        return a.due < b.due;
    });
}

ReminderModel::Occ *ReminderModel::find(const QString &occId)
{
    for (Occ &o : m_occs) if (o.id == occId) return &o;
    return nullptr;
}

// 函数 setState：改实例状态并发出变更信号
void ReminderModel::setState(Occ &o, const QString &state)
{
    touchPersist();
    o.state = state;
    emit changed();
}

// 函数 confirm：确认完成（对应后端 confirmed）
void ReminderModel::confirm(const QString &occId)
{
    if (Occ *o = find(occId)) setState(*o, QStringLiteral("confirmed"));
    queueEvent(occId, QStringLiteral("confirm"));   // 由 SyncPuller 批量 POST /v1/events
    recompute();
}

// 函数 snooze：稍后再提醒，超过次数记为未确认
void ReminderModel::snooze(const QString &occId)
{
    if (Occ *o = find(occId)) {
        if (o->snoozeLeft <= 0) {
            // 次数用尽记未确认：必须上报，否则只有本机知道，家属看板看不到
            setState(*o, QStringLiteral("missed"));
            queueEvent(occId, QStringLiteral("miss"));
        } else {
            o->snoozeLeft--;
            setState(*o, QStringLiteral("snoozed"));
            queueEvent(occId, QStringLiteral("snooze"));
        }
    }
    recompute();
}

// 函数 missed：标记这次没做（对应后端 missed）
void ReminderModel::missed(const QString &occId)
{
    if (Occ *o = find(occId)) {
        setState(*o, QStringLiteral("missed"));
        queueEvent(occId, QStringLiteral("miss"));
    }
    recompute();
}

// 函数 sos：触发呼救（由界面层发出请求）
void ReminderModel::sos()
{
    // 交给 SyncPuller → POST /v1/alarm {source:"manual", level:3}
    emit sosTriggered();
}

// 函数 doneCount：今日已完成条数
int ReminderModel::doneCount() const
{
    int n = 0;
    const QString today = QDate::currentDate().toString(Qt::ISODate);
    for (const Occ &o : m_occs)
        if (o.slotLocal.startsWith(today) && o.state == "confirmed") ++n;
    return n;
}

// 函数 recompute：按当前时间算出到期列表与今日列表
void ReminderModel::recompute()
{
    const QDateTime now = QDateTime::currentDateTime();
    const QString today = QDate::currentDate().toString(Qt::ISODate);
    m_due.clear();
    m_today.clear();
    for (const Occ &o : m_occs) {
        QVariantMap m;
        m["id"] = o.id;
        m["planId"] = o.planId;
        m["title"] = o.title;
        m["slot"] = o.slotLocal;
        m["state"] = o.state;
        m["snoozeLeft"] = o.snoozeLeft;
        m["lateMin"] = o.due.isValid() ? qMax<qint64>(0, o.due.secsTo(now) / 60) : 0;
        if (o.slotLocal.startsWith(today)) m_today << m;
        // 到期未处理（不超过 45 分钟）才进"现在该做的事"。
        // notified / escalated 也算：tick 一到点就把 pending 置成 notified，
        // 如果这里只收 pending，老人到点后反而看不到确认按钮。
        const bool active = o.state == "pending" || o.state == "notified"
                            || o.state == "escalated" || o.state == "snoozed";
        if (active && o.due <= now && o.due.secsTo(now) <= 45 * 60)
            m_due << m;
    }
    emit changed();
}

// 函数 refresh：30 秒定时重算（与后端调度节奏一致）
void ReminderModel::refresh()
{
    // 端上 tick：到点把 pending 置 notified（本机提醒），升级与 missed 仍由云端兜底
    const QDateTime now = QDateTime::currentDateTime();
    bool changedState = false;
    for (Occ &o : m_occs) {
        if (o.state != QLatin1String("pending") || !o.due.isValid())
            continue;
        if (o.due <= now) {
            o.state = QStringLiteral("notified");
            changedState = true;
        }
    }
    if (changedState) {
        touchPersist();
        emit changed();
    }
    recompute();
}

// ---------------------------------------------------------------- 远端同步
// 函数 queueEvent：把一次动作记进待上传队列（eventId 固定，重试不变）
void ReminderModel::queueEvent(const QString &occId, const QString &action, const QString &reason)
{
    touchPersist();
    PendingEvent event;
    event.occId = occId;
    event.action = action;
    event.ts = QDateTime::currentMSecsSinceEpoch();
    event.reason = reason;
    // 与后端一致：uuid5(namespace, "occurrenceId|action|client_ts")
    static const QUuid ns(QStringLiteral("7b0f7d3e-3c2a-4a55-9f0e-6b1a2c8d4e11"));
    event.eventId = QUuid::createUuidV5(
                        ns, QStringLiteral("%1|%2|%3").arg(occId, action, QString::number(event.ts)))
                        .toString(QUuid::WithoutBraces);
    m_events.append(event);
    emit eventQueued();
}

// 函数 pendingEvents：还没拿到 server_seq 的事件
QVariantList ReminderModel::pendingEvents() const
{
    QVariantList out;
    for (const PendingEvent &event : m_events) {
        if (event.serverSeq > 0)
            continue;
        QVariantMap map;
        map[QStringLiteral("eventId")] = event.eventId;
        map[QStringLiteral("occurrenceId")] = event.occId;
        map[QStringLiteral("action")] = event.action;
        map[QStringLiteral("ts")] = event.ts;
        map[QStringLiteral("reason")] = event.reason;
        out.append(map);
    }
    return out;
}

// 函数 markEventsSent：把服务端回执的 server_seq 写回本地事件
void ReminderModel::markEventsSent(const QVariantList &acks)
{
    touchPersist();
    for (const QVariant &entry : acks) {
        const QVariantMap ack = entry.toMap();
        const QString eventId = ack.value(QStringLiteral("eventId")).toString();
        const qint64 seq = ack.value(QStringLiteral("serverSeq")).toLongLong();
        for (PendingEvent &event : m_events) {
            if (event.eventId == eventId) {
                event.serverSeq = seq;
                break;
            }
        }
    }
}

// 函数 setSyncState：同步状态透给界面（offline / idle / syncing / error）
void ReminderModel::setSyncState(const QString &state)
{
    if (m_syncState == state)
        return;
    m_syncState = state;
    emit changed();
}

// 函数 applyRemotePlans：/v1/plans 的 rule（四种）→ 内部 Rule，再重建实例列表
void ReminderModel::applyRemotePlans(const QVariantList &plans)
{
    touchPersist();
    if (plans.isEmpty())
        return;
    m_rules.clear();
    for (const QVariant &entry : plans) {
        const QVariantMap src = entry.toMap();
        if (src.value(QStringLiteral("deleted")).toBool())
            continue;
        const QVariantMap rule = src.value(QStringLiteral("rule")).toMap();
        Rule r;
        r.id = QString::number(static_cast<qint64>(src.value(QStringLiteral("plan_id")).toDouble()));
        r.title = src.value(QStringLiteral("title")).toString();
        r.dose = src.value(QStringLiteral("dose")).toString();
        const QString kind = rule.value(QStringLiteral("kind")).toString();
        r.kindRule = kind.isEmpty() ? QStringLiteral("daily") : kind;
        if (r.kindRule == QLatin1String("monthly"))
            r.kindRule = QStringLiteral("daily");   // 端上骨架暂不支持每月，按每天显示
        for (const QVariant &time : rule.value(QStringLiteral("times")).toList())
            r.times << time.toString();
        for (const QVariant &day : rule.value(QStringLiteral("weekdays")).toList())
            r.weekdays << day.toInt();
        r.kind = src.value(QStringLiteral("kind")).toString();
        m_rules << r;
    }
    rebuild();
    emit changed();
}

// 函数 applyRemoteOccurrences：/v1/state 的实例直接替换本地清单（服务端为准）
void ReminderModel::applyRemoteOccurrences(const QVariantList &occurrences)
{
    touchPersist();
    if (occurrences.isEmpty())
        return;
    QList<Occ> incoming;
    for (const QVariant &entry : occurrences) {
        const QVariantMap src = entry.toMap();
        Occ o;
        o.id = QString::number(static_cast<qint64>(src.value(QStringLiteral("occurrence_id")).toDouble()));
        o.planId = QString::number(static_cast<qint64>(src.value(QStringLiteral("plan_id")).toDouble()));
        o.title = src.value(QStringLiteral("title")).toString();
        o.dose = src.value(QStringLiteral("dose")).toString();
        o.state = src.value(QStringLiteral("state")).toString();
        o.due = QDateTime::fromMSecsSinceEpoch(
            static_cast<qint64>(src.value(QStringLiteral("due_ts")).toDouble()));
        o.slotLocal = isoLocal(o.due);
        o.snoozeLeft = qMax(0, 3 - src.value(QStringLiteral("snooze_count")).toInt());
        incoming << o;
    }
    // 增量合并：/v1/state?since= 只回变化的那几条，整表替换会把当天其余提醒抹掉。
    // 同 id 覆盖字段，新 id 插入，其余保留。
    for (const Occ &o : incoming) {
        bool replaced = false;
        for (Occ &old : m_occs) {
            if (old.id == o.id) {
                old = o;
                replaced = true;
                break;
            }
        }
        if (!replaced)
            m_occs << o;
    }
    std::sort(m_occs.begin(), m_occs.end(), [](const Occ &a, const Occ &b) {
        return a.due < b.due;
    });
    recompute();
}

  // ---------------------------------------------------------------- 本地主副本
  // 函数 loadFromStoreOrDemo：冷启动读库；库里没数据才写演示规则
  void ReminderModel::loadFromStoreOrDemo()
  {
      QString error;
      QVariantList storedRules, storedOccs, storedEvents;
      qint64 cursor = 0;
      if (m_store->open(&error)
          && m_store->load(&storedRules, &storedOccs, &storedEvents, &cursor)) {
          m_rules.clear();
          for (const QVariant &entry : storedRules) {
              const QVariantMap map = entry.toMap();
              Rule r;
              r.id = map.value(QStringLiteral("id")).toString();
              r.title = map.value(QStringLiteral("title")).toString();
              r.kind = map.value(QStringLiteral("kind")).toString();
              r.kindRule = map.value(QStringLiteral("kindRule")).toString();
              r.dose = map.value(QStringLiteral("dose")).toString();
              for (const QVariant &time : map.value(QStringLiteral("times")).toList())
                  r.times << time.toString();
              for (const QVariant &day : map.value(QStringLiteral("weekdays")).toList())
                  r.weekdays << day.toInt();
              m_rules << r;
          }
          m_occs.clear();
          for (const QVariant &entry : storedOccs) {
              const QVariantMap map = entry.toMap();
              Occ o;
              o.id = map.value(QStringLiteral("id")).toString();
              o.planId = map.value(QStringLiteral("planId")).toString();
              o.title = map.value(QStringLiteral("title")).toString();
              o.slotLocal = map.value(QStringLiteral("slotLocal")).toString();
              o.state = map.value(QStringLiteral("state")).toString();
              o.due = QDateTime::fromString(o.slotLocal, QStringLiteral("yyyy-MM-dd HH:mm"));
              o.snoozeLeft = map.value(QStringLiteral("snoozeLeft")).toInt();
              m_occs << o;
          }
          m_events.clear();
          for (const QVariant &entry : storedEvents) {
              const QVariantMap map = entry.toMap();
              PendingEvent event;
              event.eventId = map.value(QStringLiteral("eventId")).toString();
              event.occId = map.value(QStringLiteral("occurrenceId")).toString();
              event.action = map.value(QStringLiteral("action")).toString();
              event.ts = map.value(QStringLiteral("ts")).toLongLong();
              event.serverSeq = map.value(QStringLiteral("serverSeq")).toLongLong();
              event.reason = map.value(QStringLiteral("reason")).toString();
              m_events << event;
          }
          Q_UNUSED(cursor)
          recompute();
          return;
      }
      loadDemo();
  }

  // 函数 touchPersist：变更后 1 秒防抖落盘
  void ReminderModel::touchPersist()
  {
      if (m_store && m_store->isOpen() && !m_saveTimer.isActive())
          m_saveTimer.start();
  }

  // 函数 persistNow：把规则/实例/事件整表写进 SQLite（单事务）
  void ReminderModel::persistNow()
  {
      if (!m_store || !m_store->isOpen())
          return;
      QVariantList rules, occs, events;
      for (const Rule &r : m_rules) {
          QVariantMap map;
          map[QStringLiteral("id")] = r.id;
          map[QStringLiteral("title")] = r.title;
          map[QStringLiteral("kind")] = r.kind;
          map[QStringLiteral("kindRule")] = r.kindRule;
          map[QStringLiteral("dose")] = r.dose;
          map[QStringLiteral("times")] = r.times;
          QVariantList weekdays;
          for (int day : r.weekdays)
              weekdays << day;
          map[QStringLiteral("weekdays")] = weekdays;
          rules << map;
      }
      for (const Occ &o : m_occs) {
          QVariantMap map;
          map[QStringLiteral("id")] = o.id;
          map[QStringLiteral("planId")] = o.planId;
          map[QStringLiteral("title")] = o.title;
          map[QStringLiteral("slotLocal")] = o.slotLocal;
          map[QStringLiteral("state")] = o.state;
          map[QStringLiteral("snoozeLeft")] = o.snoozeLeft;
          occs << map;
      }
      for (const PendingEvent &event : m_events) {
          QVariantMap map;
          map[QStringLiteral("eventId")] = event.eventId;
          map[QStringLiteral("occurrenceId")] = event.occId;
          map[QStringLiteral("action")] = event.action;
          map[QStringLiteral("ts")] = event.ts;
          map[QStringLiteral("serverSeq")] = event.serverSeq;
          map[QStringLiteral("reason")] = event.reason;
          events << map;
      }
      m_store->save(rules, occs, events);
  }

  // 函数 serverCursor / setServerCursor：/v1/state 的增量游标
  qint64 ReminderModel::serverCursor() const
  {
      return m_store ? m_store->cursor() : 0;
  }

  void ReminderModel::setServerCursor(qint64 seq)
  {
      if (m_store)
          m_store->setCursor(seq);
  }

  // 函数 localDbPath：本地库路径（设置页/排障用）
  QString ReminderModel::localDbPath() const
  {
      return m_store ? m_store->path() : QString();
  }
