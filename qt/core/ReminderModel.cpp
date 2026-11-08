// 作用：Qt 规则模型的实现：七种规则展开、30 秒刷新到期判断（对照后端 slots_on/transition）
#include "ReminderModel.h"

#include <QDebug>

ReminderModel::ReminderModel(QObject *parent) : QObject(parent)
{
    // 30 秒刷新一次到期判断：与后端 scheduler 的 30 s 节奏一致
    m_tick.setInterval(30 * 1000);
    connect(&m_tick, &QTimer::timeout, this, &ReminderModel::refresh);
    m_tick.start();
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
    o.state = state;
    emit changed();
}

// 函数 confirm：确认完成（对应后端 confirmed）
void ReminderModel::confirm(const QString &occId)
{
    if (Occ *o = find(occId)) setState(*o, QStringLiteral("confirmed"));
    // TODO(联调)：POST /api/v1/occurrences/{id}/events {action:"confirmed", event_id, client_ts}
    recompute();
}

// 函数 snooze：稍后再提醒，超过次数记为未确认
void ReminderModel::snooze(const QString &occId)
{
    if (Occ *o = find(occId)) {
        if (o->snoozeLeft <= 0) setState(*o, QStringLiteral("missed"));
        else { o->snoozeLeft--; setState(*o, QStringLiteral("snoozed")); }
    }
    recompute();
}

// 函数 missed：标记这次没做（对应后端 missed）
void ReminderModel::missed(const QString &occId)
{
    if (Occ *o = find(occId)) setState(*o, QStringLiteral("missed"));
    recompute();
}

// 函数 sos：触发呼救（由界面层发出请求）
void ReminderModel::sos()
{
    // 后端接口：POST /api/v1/sos {device, note}
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
        // 到期未处理（不超过 45 分钟）才进"现在该做的事"
        if (o.state == "pending" && o.due <= now && o.due.secsTo(now) <= 45 * 60)
            m_due << m;
    }
    emit changed();
}

// 函数 refresh：30 秒定时重算（与后端调度节奏一致）
void ReminderModel::refresh()
{
    // 到期判断每 30 秒用本地时钟重算一次；真正的状态仍以服务端返回为准
    recompute();
}

