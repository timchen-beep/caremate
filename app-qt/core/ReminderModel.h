// 作用：Qt 规则模型的接口：规则→实例、确认/稍后/未做、到期列表
#include <QObject>
#include <QString>
#include <QVariantList>
#include <QTimer>
#include <QDateTime>

// 规则 → 实例（对应后端 slots_on / meal_slots 的 C++ 版）
// 只做三件事：展开规则、算出到期时刻、维护实例状态。
// 提醒的"不丢不重"仍以服务端为准；这里的状态用于离线时先给老人看。
class ReminderModel : public QObject
{
    Q_OBJECT
    Q_PROPERTY(QVariantList dueList READ dueList NOTIFY changed)
    Q_PROPERTY(QVariantList todayList READ todayList NOTIFY changed)
    Q_PROPERTY(int doneCount READ doneCount NOTIFY changed)
    Q_PROPERTY(QString bindCode READ bindCode CONSTANT)

public:
    explicit ReminderModel(QObject *parent = nullptr);

    QVariantList dueList() const { return m_due; }
    QVariantList todayList() const { return m_today; }
    int doneCount() const;
    QString bindCode() const { return QStringLiteral("8823"); }

    Q_INVOKABLE void loadDemo();
    Q_INVOKABLE void refresh();
    Q_INVOKABLE void confirm(const QString &occId);
    Q_INVOKABLE void snooze(const QString &occId);
    Q_INVOKABLE void missed(const QString &occId);
    Q_INVOKABLE void sos();

signals:
    void changed();
    void sosTriggered();

private:
    struct Rule {
        QString id, title, kind;      // medication / water / activity
        QStringList times;            // "08:00"
        QString kindRule = "daily";   // daily / weekly / interval / once
        QList<int> weekdays;          // 1..7
        int intervalN = 2;
        QString startDate;            // yyyy-MM-dd
        QString dose;
    };
    struct Occ {
        QString id, planId, title, slotLocal, state;
        QDateTime due;
        int snoozeLeft = 3;
    };

    QList<Rule> m_rules;
    QList<Occ> m_occs;
    QVariantList m_due, m_today;
    QTimer m_tick;

    void rebuild();                      // 规则 → 未来 3 天实例
    bool matches(const Rule &r, const QDate &d) const;
    Occ *find(const QString &occId);
    void recompute();
    void setState(Occ &o, const QString &state);
    static QString isoLocal(const QDateTime &dt);
};

