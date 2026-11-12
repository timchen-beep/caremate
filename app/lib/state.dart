// 作用：全局状态与动作：冷启动读本地主副本、点确认/稍后、事件入本地库、批量上行、按游标回灌合并
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api.dart';
import 'local_db.dart';
import 'models.dart';

/// 应用状态：本地队列优先（契约 §5），状态以云端为准（契约 §4）
class AppState extends ChangeNotifier {
  late SharedPreferences _prefs;

  String userId = 'u-elder';
  String baseUrl = const String.fromEnvironment(
    'API_BASE',
    defaultValue: 'http://10.0.2.2:8000', // Android 模拟器访问宿主机
  );
  String token = const String.fromEnvironment(
    'API_TOKEN',
    defaultValue: 'app-elder-001',
  );
  String pairingCode = '';

  List<Plan> plans = [];
  List<Occurrence> occurrences = [];
  List<AppEvent> events = [];
  List<DueItem> due = [];
  String? lastError;
  bool syncing = false;
  String? lastSyncAt;

  ApiClient get api => ApiClient(baseUrl: baseUrl, token: token);

  // ---------------------------------------------------------------- 初始化
  Future<void> init() async {
    _prefs = await SharedPreferences.getInstance();
    userId = _prefs.getString('userId') ?? 'u-elder';
    baseUrl = _prefs.getString('baseUrl') ?? baseUrl;
    token = _prefs.getString('token') ?? token;

    // ① 冷启动先读本地主副本（4.1 架构图第 3 层）：断网也能看到今天的计划
    try {
      await LocalDb.open();
      final local = await LocalDb.occurrencesForDate(dateOf(DateTime.now()));
      if (local.isNotEmpty) occurrences = local;
      final cached = await LocalDb.loadPlans();
      if (cached.isNotEmpty) plans = cached;
      events = await LocalDb.pendingEvents();
    } catch (_) {
      // 本地库不可用（如首次运行权限问题）时退回旧路径，不让 App 起不来
      events = _readList('events').map((e) => AppEvent.fromJson(e)).toList();
    }

    recomputeDue();
    notifyListeners();
  }

  List<Map<String, dynamic>> _readList(String key) {
    final raw = _prefs.getString(key);
    if (raw == null || raw.isEmpty) return [];
    try {
      return (jsonDecode(raw) as List).map((e) => Map<String, dynamic>.from(e as Map)).toList();
    } catch (_) {
      return [];
    }
  }

  // 函数 _persist：把待同步队列与设置写入本地存储（断网也不丢）
  Future<void> _persist() async {
    await _prefs.setString('events', jsonEncode(events.map((e) => e.toJson()).toList()));
    await _prefs.setString('userId', userId);
    await _prefs.setString('baseUrl', baseUrl);
    await _prefs.setString('token', token);
  }

  // ---------------------------------------------------------------- 待办
  /// 待办来自云端实例（状态只由后端改），本地只负责把动作排队。
  /// 三条过滤缺一不可：
  /// 1) 已经确认/记未确认的（本地刚点过、还没同步回来的）不再出现；
  ///     但"稍后提醒"要留着，否则点了等会儿它就消失、再也不会弹回来；
  /// 2) 还没到点的不能进待办（否则上午 9 点就把 20:00 的药摆出来，还能提前确认）；
  /// 3) 按时间正序，最早到点的排第一。
  void recomputeDue() {
    final out = <DueItem>[];
    final nowLocal = slotOf(DateTime.now());     // "2026-11-12 09:03"
    for (final o in occurrences) {
      if (!o.actionable) continue;
      final settled = events.any((e) =>
          e.occurrenceId == o.id &&
          (e.action == 'confirmed' || e.action == 'missed'));
      if (settled) continue;
      if (o.slotLocal.isNotEmpty && o.slotLocal.compareTo(nowLocal) > 0) continue;
      out.add(DueItem(
        occurrenceId: o.id,
        planId: o.planId,
        title: o.title,
        slotLocal: o.slotLocal,
        lateMin: o.lateMin,
        snoozeLeft: o.snoozeLeft,
      ));
    }
    out.sort((a, b) => a.slotLocal.compareTo(b.slotLocal));
    due = out;
  }

  // ---------------------------------------------------------------- 动作
  /// 契约 §4/§5：本地入队一条事件（写 prefs + 本地库 events 表），状态等云端返回
  Future<void> record(Occurrence occ, String action) async {
    final clientTs = isoNow();
    final id = AppEvent.buildEventId(occ.id, action, clientTs);
    if (events.any((e) => e.eventId == id)) return;

    events.insert(
      0,
      AppEvent(
        eventId: id,
        occurrenceId: occ.id,
        planId: occ.planId,
        title: occ.title,
        slotLocal: occ.slotLocal,
        action: action,
        clientTs: clientTs,
        synced: false,
      ),
    );
    await _persist();
    try {
      await LocalDb.queueEvent(events.first);
    } catch (_) {}
    notifyListeners();
    await pushPending();
  }

  /// 优先批量上行（POST /events），按 rejected 索引只重发被拒条目；批量失败退回逐条；
  /// client_ts 保持原样，duplicate=true 也算成功（契约 §5）
  Future<void> pushPending() async {
    final pending = events.where((e) => !e.synced).toList();
    if (pending.isEmpty) return;

    // 优先走批量上行（4.1 架构图第 5 层）：一次请求补传整条队列
    try {
      final payload = pending
          .map((e) => {
                'occurrence_id': e.occurrenceId,
                'action': e.action,
                'client_ts': e.clientTs,
                'event_id': e.eventId,
              })
          .toList();
      final res = await api.pushEventsBatch(payload);
      final rejected = (res['rejected'] as List?) ?? const [];
      final okCount = (res['accepted'] as int? ?? 0) + (res['duplicates'] as int? ?? 0);
      if (okCount > 0) {
        final rejectedIds = <String>{};
        for (final r in rejected) {
          final idx = (r['index'] as int?) ?? -1;
          if (idx >= 0 && idx < pending.length) rejectedIds.add(pending[idx].eventId);
        }
        for (final e in pending) {
          if (!rejectedIds.contains(e.eventId)) e.synced = true;
        }
        try {
          await LocalDb.markEventsSynced(
              pending.where((e) => e.synced).map((e) => e.eventId).toList());
        } catch (_) {}
        await _persist();
        notifyListeners();
        if (rejectedIds.isEmpty) return;
      }
    } catch (_) {
      // 批量失败就退回逐条（老路径），保证弱网也能补传
    }

    for (final e in pending) {
      try {
        await api.pushEvent(
          occurrenceId: e.occurrenceId,
          action: e.action,
          eventId: e.eventId,
          clientTs: e.clientTs,
        );
        e.synced = true;
      } on ApiException catch (err) {
        lastError = '上行失败：$err';
        if (err.permanent) break;
        if (err.goPair) break;
      } catch (err) {
        lastError = '上行失败：$err';
        break;
      }
    }
    await _persist();
    notifyListeners();
  }

  // ---------------------------------------------------------------- 同步
  /// 先按游标回灌（GET /state?since=）写本地，再取整包合并：
  /// 本地已有的（端上 tick 改过的 notified）与云端返回的取并集，云端字段优先（云端才有 escalated/missed）
  Future<void> sync() async {
    syncing = true;
    lastError = null;
    notifyListeners();
    try {
      // ① 先回灌：按游标拉服务端变化（4.1 架构图第 5 层下行）
      final cursor = await LocalDb.getCursor();
      final state = await api.fetchStateSince(cursor);
      final remoteOcc = ((state['occurrences'] as List?) ?? const [])
          .map((e) => Occurrence.fromJson(Map<String, dynamic>.from(e as Map)))
          .toList();
      if (remoteOcc.isNotEmpty) {
        await LocalDb.saveOccurrences(remoteOcc);
      }
      // 游标即使本页没有实例也要推进：只改了记录（revision+1）时 next_since 也会前进
      final nextCursor = (state['cursor'] ?? '').toString();
      if (nextCursor.isNotEmpty) {
        await LocalDb.setCursor(nextCursor);
      }

      // ② 再取整包（兼容旧服务端），并用「本地优先 + 云端覆盖」合并
      final b = await api.fetchBundle();
      if (b.plans.isNotEmpty) {
        plans = b.plans;
        try {
          await LocalDb.savePlans(b.plans);
        } catch (_) {}
      }
      final merged = <String, Occurrence>{};
      for (final o in occurrences) {
        merged[o.id] = o; // 本地已有（可能是端上 tick 改过的 notified）
      }
      for (final o in b.occurrences) {
        merged[o.id] = o; // 云端为准（云端才有 escalated / missed）
      }
      occurrences = merged.values.toList();
      try {
        await LocalDb.saveOccurrences(occurrences);
      } catch (_) {}
      recomputeDue();
      lastSyncAt = DateTime.now().toString().substring(11, 16);
      await _persist();
      await pushPending();
    } on ApiException catch (err) {
      lastError = '$err';
    } catch (err) {
      lastError = '离线：$err';
    } finally {
      syncing = false;
      notifyListeners();
    }
  }

  // 函数 pair：用配对码换取令牌
  Future<void> pair(String code) async {
    final j = await api.pair(code);
    token = (j['token'] ?? '').toString();
    userId = (j['elder_id'] ?? userId).toString();
    pairingCode = code;
    await _persist();
    await sync();
  }

  // 函数 saveSettings：保存服务器地址/令牌并立即重新同步
  Future<void> saveSettings({String? url, String? tk}) async {
    if (url != null && url.trim().isNotEmpty) baseUrl = url.trim().replaceAll(RegExp(r'/$'), '');
    if (tk != null && tk.trim().isNotEmpty) token = tk.trim();
    await _persist();
    notifyListeners();
  }

  // ---------------------------------------------------------------- 统计（展示用）
  List<Occurrence> todayOccurrences() {
    final today = dateOf(DateTime.now());
    return occurrences.where((o) => o.slotLocal.startsWith(today)).toList();
  }

  // 函数 todayEvents：筛选出今天的动作记录
  List<AppEvent> todayEvents() {
    final today = dateOf(DateTime.now());
    return events.where((e) => e.slotLocal.startsWith(today)).toList();
  }
}

