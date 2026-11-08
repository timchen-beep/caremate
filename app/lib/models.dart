// 作用：数据模型：Occurrence / Plan / AppEvent，字段与契约 v0.1 一一对应
/// 状态枚举（契约 §4，不要自己造词）
const kStates = ['pending', 'notified', 'snoozed', 'confirmed', 'missed', 'escalated'];

const kStateLabel = {
  'pending': '待提醒',
  'notified': '已提醒',
  'snoozed': '稍后再说',
  'confirmed': '已确认',
  'missed': '未确认',
  'escalated': '已通知家属',
};

/// 提醒计划（云端下发，App 本地缓存）
class Plan {
  final String id;
  final String title;
  final String kind; // medication / water / activity / meal
  final List<String> times; // "08:00"
  final List<int> weekdays; // 1..7
  final String dose;
  final String note;
  final bool active;
  final Map<String, dynamic> rule; // 契约 §3

  Plan({
    required this.id,
    required this.title,
    required this.kind,
    required this.times,
    required this.weekdays,
    this.dose = '',
    this.note = '',
    required this.active,
    this.rule = const {'kind': 'daily'},
  });

  factory Plan.fromJson(Map<String, dynamic> j) {
    final rawTimes = j['times'];
    final rawDays = j['weekdays'];
    return Plan(
      id: (j['id'] ?? '').toString(),
      title: (j['title'] ?? '未命名计划').toString(),
      kind: (j['kind'] ?? 'medication').toString(),
      times: rawTimes is List
          ? rawTimes.map((e) => e.toString()).toList()
          : (rawTimes ?? '').toString().split(',').where((e) => e.isNotEmpty).toList(),
      weekdays: rawDays is List
          ? rawDays.map((e) => int.tryParse(e.toString()) ?? 0).where((e) => e >= 1 && e <= 7).toList()
          : (rawDays ?? '1,2,3,4,5,6,7')
              .toString()
              .split(',')
              .map((e) => int.tryParse(e) ?? 0)
              .where((e) => e >= 1 && e <= 7)
              .toList(),
      dose: (j['dose'] ?? '').toString(),
      note: (j['note'] ?? '').toString(),
      active: j['active'] == true || j['active'] == 1,
      rule: j['rule'] is Map ? Map<String, dynamic>.from(j['rule'] as Map) : const {'kind': 'daily'},
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'title': title,
        'kind': kind,
        'times': times,
        'weekdays': weekdays,
        'dose': dose,
        'note': note,
        'active': active,
        'rule': rule,
      };

  String get kindLabel =>
      const {'medication': '用药', 'water': '饮水', 'activity': '活动', 'meal': '餐食'}[kind] ?? kind;

  /// 该计划今天剩下的时刻（一次性/疗程等由云端物化，这里只做兜底）
  List<String> timesToday() {
    final wd = DateTime.now().weekday;
    final kind = (rule['kind'] ?? 'daily').toString();
    if (!active) return const [];
    if (kind == 'once') {
      final at = (rule['at'] ?? rule['date'] ?? '').toString();
      if (!at.startsWith(dateOf(DateTime.now()))) return const [];
    } else if (kind != 'interval' && kind != 'monthly' && kind != 'course') {
      if (!weekdays.contains(wd)) return const [];
    }
    return times;
  }
}

/// 一个实例（契约 §3/§4：状态只由后端改，App 只显示）
class Occurrence {
  final String id;
  final String planId;
  final String title;
  final String dose;
  final String slotLocal; // "2026-11-05 08:00"（本地墙钟）
  final String dueAtUtc; // "2026-11-05T00:00:00Z"
  final String state;
  final int level;
  final int lateMin;
  final int snoozeLeft;
  final String notifiedLocal;
  final String confirmedAt;

  Occurrence({
    required this.id,
    required this.planId,
    required this.title,
    required this.dose,
    required this.slotLocal,
    required this.dueAtUtc,
    required this.state,
    required this.level,
    required this.lateMin,
    required this.snoozeLeft,
    required this.notifiedLocal,
    required this.confirmedAt,
  });

  factory Occurrence.fromJson(Map<String, dynamic> j) => Occurrence(
        id: (j['id'] ?? '').toString(),
        planId: (j['plan_id'] ?? '').toString(),
        title: (j['title'] ?? '').toString(),
        dose: (j['dose'] ?? '').toString(),
        slotLocal: (j['slot_local'] ?? j['slot'] ?? '').toString(),
        dueAtUtc: (j['due_at_utc'] ?? '').toString(),
        state: (j['state'] ?? 'pending').toString(),
        level: int.tryParse('${j['level']}') ?? 0,
        lateMin: int.tryParse('${j['late_min']}') ?? 0,
        snoozeLeft: int.tryParse('${j['snooze_left']}') ?? 0,
        notifiedLocal: (j['notified_local'] ?? '').toString(),
        confirmedAt: (j['confirmed_at'] ?? '').toString(),
      );

  String get stateLabel => kStateLabel[state] ?? state;
  bool get actionable => const ['pending', 'notified', 'snoozed', 'escalated'].contains(state);
}

/// 本地待同步事件（契约 §5：event_id 与 client_ts 固定，重试原样重发）
class AppEvent {
  final String eventId;
  final String occurrenceId;
  final String planId;
  final String title;
  final String slotLocal;
  final String action; // confirmed / snoozed / missed
  final String clientTs; // ISO 8601，重试不得变
  bool synced;

  AppEvent({
    required this.eventId,
    required this.occurrenceId,
    required this.planId,
    required this.title,
    required this.slotLocal,
    required this.action,
    required this.clientTs,
    this.synced = false,
  });

  factory AppEvent.fromJson(Map<String, dynamic> j) => AppEvent(
        eventId: (j['event_id'] ?? j['eventId'] ?? '').toString(),
        occurrenceId: (j['occurrence_id'] ?? j['occurrenceId'] ?? '').toString(),
        planId: (j['plan_id'] ?? j['planId'] ?? '').toString(),
        title: (j['title'] ?? '').toString(),
        slotLocal: (j['slot_local'] ?? j['slot'] ?? '').toString(),
        action: (j['action'] ?? j['status'] ?? 'confirmed').toString(),
        clientTs: (j['client_ts'] ?? j['created_at'] ?? '').toString(),
        synced: j['synced'] != false,
      );

  Map<String, dynamic> toJson() => {
        'event_id': eventId,
        'occurrence_id': occurrenceId,
        'plan_id': planId,
        'title': title,
        'slot_local': slotLocal,
        'action': action,
        'client_ts': clientTs,
        'synced': synced,
      };

  String get statusLabel =>
      const {'confirmed': '已确认', 'snoozed': '稍后提醒', 'missed': '未确认'}[action] ?? action;

  /// 契约 §5：uuid5(occurrence_id + action + client_ts)。
  /// Dart 侧用稳定的字符串键代替 uuid5，服务端以客户端给的 event_id 为准。
  static String buildEventId(String occurrenceId, String action, String clientTs) =>
      'ev:$occurrenceId:$action:$clientTs';
}

String pad2(int n) => n.toString().padLeft(2, '0');
String dateOf(DateTime d) => '${d.year}-${pad2(d.month)}-${pad2(d.day)}';
String slotOf(DateTime d) => '${dateOf(d)} ${pad2(d.hour)}:${pad2(d.minute)}';

/// 契约 §6：ISO 8601 带时区
String isoNow() {
  final d = DateTime.now();
  final off = d.timeZoneOffset;
  final sign = off.isNegative ? '-' : '+';
  final hh = pad2(off.inHours.abs());
  final mm = pad2(off.inMinutes.abs() % 60);
  return '${dateOf(d)}T${pad2(d.hour)}:${pad2(d.minute)}:${pad2(d.second)}$sign$hh:$mm';
}

/// 首页待办（由云端实例派生，App 不再自己算状态）
class DueItem {
  final String occurrenceId;
  final String planId;
  final String title;
  final String slotLocal;
  final int lateMin;
  final int snoozeLeft;

  DueItem({
    required this.occurrenceId,
    required this.planId,
    required this.title,
    required this.slotLocal,
    required this.lateMin,
    required this.snoozeLeft,
  });
}
