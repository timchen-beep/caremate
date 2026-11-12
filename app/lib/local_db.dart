// 作用：手机端本地库（4.1 架构图第 3 层）：plans / occurrences / events 三表 + 同步游标，冷启动先读这里
import 'dart:convert';

import 'package:path/path.dart' as p;
import 'package:sqflite/sqflite.dart';

import 'models.dart';

/// 手机端主副本。
///
/// 设计要点（对应 4.1 架构图）：
/// - 冷启动只读本地表，不读网络：断网也能看到今天的计划
/// - events 表以 event_id 为主键，重复入队自动忽略（幂等）
/// - meta 表存同步游标，供 GET /v1/state?since= 增量回灌
class LocalDb {
  static Database? _db;

  static Future<Database> open() async {
    if (_db != null) return _db!;
    final dir = await getDatabasesPath();
    _db = await openDatabase(
      p.join(dir, 'caremate.db'),
      version: 1,
      onCreate: (db, version) async {
        await db.execute('''
          CREATE TABLE plans(
            id TEXT PRIMARY KEY, title TEXT, kind TEXT, times TEXT, dose TEXT,
            note TEXT, active INTEGER, rule TEXT
          )''');
        await db.execute('''
          CREATE TABLE occurrences(
            id TEXT PRIMARY KEY, plan_id TEXT, slot_local TEXT, due_at_utc TEXT,
            title TEXT, dose TEXT, state TEXT, level INTEGER, late_min INTEGER,
            snooze_left INTEGER, notified_local TEXT, confirmed_at TEXT,
            updated_at TEXT
          )''');
        await db.execute('''
          CREATE TABLE events(
            event_id TEXT PRIMARY KEY, occurrence_id TEXT, plan_id TEXT, title TEXT,
            slot_local TEXT, action TEXT, client_ts TEXT, synced INTEGER DEFAULT 0
          )''');
        await db.execute('CREATE TABLE meta(k TEXT PRIMARY KEY, v TEXT)');
        await db.execute('CREATE INDEX idx_occ_date ON occurrences(slot_local)');
      },
    );
    return _db!;
  }

  // ---------------------------------------------------------------- 计划
  static Future<void> savePlans(List<Plan> plans) async {
    final db = await open();
    final batch = db.batch();
    for (final plan in plans) {
      batch.insert('plans', {
        'id': plan.id,
        'title': plan.title,
        'kind': plan.kind,
        'times': plan.times.join(','),
        'dose': plan.dose,
        'note': plan.note,
        'active': plan.active ? 1 : 0,
        'rule': plan.rule.toString(),
      }, conflictAlgorithm: ConflictAlgorithm.replace);
    }
    await batch.commit(noResult: true);
  }

  static Future<List<Plan>> loadPlans() async {
    final db = await open();
    final rows = await db.query('plans');
    return rows.map((r) {
      // rule 存的是 JSON 字符串（savePlans 里 plan.rule.toString() 的结果），
      // 原来这里硬编码成 {'kind':'daily'}，周计划读回来就变成每天都提醒。
      Map<String, dynamic> rule = const {'kind': 'daily'};
      final raw = (r['rule'] ?? '').toString();
      if (raw.startsWith('{')) {
        try {
          rule = Map<String, dynamic>.from(jsonDecode(raw) as Map);
        } catch (_) {
          // 解析不了就退回每天，至少不崩
        }
      }
      return Plan.fromJson({
        'id': r['id'],
        'title': r['title'],
        'kind': r['kind'],
        'times': r['times'],
        'dose': r['dose'],
        'note': r['note'],
        'active': r['active'],
        'rule': rule,
        // 周几存在 rule.weekdays 里，一起还原，别丢
        'weekdays': rule['weekdays'],
      });
    }).toList();
  }

  // ---------------------------------------------------------------- 实例
  static Future<void> saveOccurrences(List<Occurrence> list) async {
    final db = await open();
    final now = DateTime.now().toUtc().toIso8601String();
    final batch = db.batch();
    for (final o in list) {
      batch.insert('occurrences', {
        'id': o.id,
        'plan_id': o.planId,
        'slot_local': o.slotLocal,
        'due_at_utc': o.dueAtUtc,
        'title': o.title,
        'dose': o.dose,
        'state': o.state,
        'level': o.level,
        'late_min': o.lateMin,
        'snooze_left': o.snoozeLeft,
        'notified_local': o.notifiedLocal,
        'confirmed_at': o.confirmedAt,
        'updated_at': now,
      }, conflictAlgorithm: ConflictAlgorithm.replace);
    }
    await batch.commit(noResult: true);
  }

  static Future<List<Occurrence>> occurrencesForDate(String ymd) async {
    final db = await open();
    final rows = await db.query('occurrences',
        where: 'slot_local LIKE ?', whereArgs: ['$ymd%'], orderBy: 'slot_local');
    return rows
        .map((r) => Occurrence.fromJson({
              'id': r['id'],
              'plan_id': r['plan_id'],
              'slot_local': r['slot_local'],
              'due_at_utc': r['due_at_utc'],
              'title': r['title'],
              'dose': r['dose'],
              'state': r['state'],
              'level': r['level'],
              'late_min': r['late_min'],
              'snooze_left': r['snooze_left'],
              'notified_local': r['notified_local'],
              'confirmed_at': r['confirmed_at'],
            }))
        .toList();
  }

  static Future<int> countOccurrences() async {
    final db = await open();
    final rows = await db.rawQuery('SELECT COUNT(*) AS c FROM occurrences');
    return Sqflite.firstIntValue(rows) ?? 0;
  }

  /// 端上 tick：把到点且仍为 pending 的本地实例置为 notified（只改本地展示，权威状态在云端）
  static Future<int> markNotified(String occurrenceId, String at) async {
    final db = await open();
    return db.update('occurrences', {'state': 'notified', 'notified_local': at, 'updated_at': at},
        where: 'id=? AND state=?', whereArgs: [occurrenceId, 'pending']);
  }

  // ---------------------------------------------------------------- 事件
  /// 入队一条动作；event_id 重复时忽略（幂等）
  static Future<void> queueEvent(AppEvent e) async {
    final db = await open();
    await db.insert('events', {
      'event_id': e.eventId,
      'occurrence_id': e.occurrenceId,
      'plan_id': e.planId,
      'title': e.title,
      'slot_local': e.slotLocal,
      'action': e.action,
      'client_ts': e.clientTs,
      'synced': e.synced ? 1 : 0,
    }, conflictAlgorithm: ConflictAlgorithm.ignore);
  }

  static Future<List<AppEvent>> pendingEvents() async {
    final db = await open();
    final rows = await db.query('events', where: 'synced=0', orderBy: 'client_ts');
    return rows
        .map((r) => AppEvent(
              eventId: r['event_id'] as String,
              occurrenceId: r['occurrence_id'] as String,
              planId: (r['plan_id'] ?? '') as String,
              title: (r['title'] ?? '') as String,
              slotLocal: (r['slot_local'] ?? '') as String,
              action: r['action'] as String,
              clientTs: r['client_ts'] as String,
              synced: false,
            ))
        .toList();
  }

  static Future<void> markEventsSynced(List<String> eventIds) async {
    if (eventIds.isEmpty) return;
    final db = await open();
    final marks = List.filled(eventIds.length, '?').join(',');
    await db.rawUpdate('UPDATE events SET synced=1 WHERE event_id IN ($marks)', eventIds);
  }

  // ---------------------------------------------------------------- 游标
  // 游标存成 "时间|id" 两段：服务端 updated_at 只到秒，同一秒里的一批变化必须靠 id 续上，
  // 否则翻页时同一秒里剩下的行会被永久跳过（家属端少记录就是这么来的）。
  static Future<String> getCursor() async {
    final db = await open();
    final rows = await db.query('meta', where: 'k=?', whereArgs: ['since']);
    return rows.isEmpty ? '' : (rows.first['v'] as String? ?? '');
  }

  static Future<void> setCursor(String cursor) async {
    if (cursor.isEmpty) return;
    final db = await open();
    await db.insert('meta', {'k': 'since', 'v': cursor},
        conflictAlgorithm: ConflictAlgorithm.replace);
  }
}