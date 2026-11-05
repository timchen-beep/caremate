import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api.dart';
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
    events = _readList('events').map((e) => AppEvent.fromJson(e)).toList();
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

  Future<void> _persist() async {
    await _prefs.setString('events', jsonEncode(events.map((e) => e.toJson()).toList()));
    await _prefs.setString('userId', userId);
    await _prefs.setString('baseUrl', baseUrl);
    await _prefs.setString('token', token);
  }

  // ---------------------------------------------------------------- 待办
  /// 待办来自云端实例（状态只由后端改），本地只负责把动作排队
  void recomputeDue() {
    final out = <DueItem>[];
    for (final o in occurrences) {
      if (!o.actionable) continue;
      if (events.any((e) => e.occurrenceId == o.id)) continue;
      out.add(DueItem(
        occurrenceId: o.id,
        planId: o.planId,
        title: o.title,
        slotLocal: o.slotLocal,
        lateMin: o.lateMin,
        snoozeLeft: o.snoozeLeft,
      ));
    }
    out.sort((a, b) => b.slotLocal.compareTo(a.slotLocal));
    due = out;
  }

  // ---------------------------------------------------------------- 动作
  /// 契约 §4/§5：本地只入队一条事件，状态等云端返回
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
    notifyListeners();
    await pushPending();
  }

  /// 逐条上行；client_ts 保持原样，duplicate=true 也算成功（契约 §5）
  Future<void> pushPending() async {
    final pending = events.where((e) => !e.synced).toList();
    if (pending.isEmpty) return;
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
  Future<void> sync() async {
    syncing = true;
    lastError = null;
    notifyListeners();
    try {
      final b = await api.fetchBundle();
      if (b.plans.isNotEmpty) plans = b.plans;
      occurrences = b.occurrences;
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

  Future<void> pair(String code) async {
    final j = await api.pair(code);
    token = (j['token'] ?? '').toString();
    userId = (j['elder_id'] ?? userId).toString();
    pairingCode = code;
    await _persist();
    await sync();
  }

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

  List<AppEvent> todayEvents() {
    final today = dateOf(DateTime.now());
    return events.where((e) => e.slotLocal.startsWith(today)).toList();
  }
}
