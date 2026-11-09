// 作用：HTTP 客户端：Bearer 令牌、JSON 编解码、错误码映射，含端云同步两条（/state?since= 回灌、/events 批量上行）
import 'dart:convert';

import 'package:http/http.dart' as http;

import 'models.dart';

class ApiException implements Exception {
  ApiException(this.message, {this.status = 0});
  final String message;
  final int status;
  @override
  String toString() => message;

  /// 契约 §7：401 回配对页、403 不重试、404/409 刷新、422 开发期看返回
  bool get goPair => status == 401;
  bool get refresh => status == 404 || status == 409;
  bool get permanent => status == 403;
}

/// 一次拉取的合并结果：计划 + 待办 + 今日实例
class Bundle {
  Bundle({required this.plans, required this.due, required this.occurrences});
  final List<Plan> plans;
  final List<DueItem> due;
  final List<Occurrence> occurrences;
}

/// 契约 v0.1：Authorization: Bearer，七个接口
class ApiClient {
  ApiClient({required this.baseUrl, required this.token});

  final String baseUrl;
  final String token;

  /// 契约 §6：一律 ISO 8601 带时区
  static String isoNow() => DateTime.now().toIso8601String();

  Uri _u(String path, [Map<String, String>? q]) =>
      Uri.parse('$baseUrl$path').replace(queryParameters: q);

  Map<String, String> get _headers => {
        'Content-Type': 'application/json; charset=utf-8',
        'Authorization': 'Bearer $token',
      };

  dynamic _decode(http.Response r) {
    final text = utf8.decode(r.bodyBytes);
    final dynamic body = text.isEmpty ? null : jsonDecode(text);
    if (r.statusCode >= 400) {
      final msg = body is Map ? body['error']?.toString() : text;
      throw ApiException(msg ?? 'HTTP ${r.statusCode}', status: r.statusCode);
    }
    return body;
  }

  // 函数 _get：GET 封装：带 Bearer、超时、错误码映射
  Future<dynamic> _get(String path, [Map<String, String>? q]) async {
    final r = await http.get(_u(path, q), headers: _headers).timeout(const Duration(seconds: 8));
    return _decode(r);
  }

  // 函数 _send：写操作封装（POST/PATCH）：序列化 + 错误处理
  Future<dynamic> _send(String method, String path, Map<String, dynamic> data) async {
    final req = http.Request(method, _u(path))
      ..headers.addAll(_headers)
      ..body = jsonEncode(data);
    final streamed = await req.send().timeout(const Duration(seconds: 8));
    return _decode(await http.Response.fromStream(streamed));
  }

  /// 1) 配对：pairing_code → elder_id, token
  Future<Map<String, dynamic>> pair(String pairingCode) async {
    final j = await _send('POST', '/api/v1/auth/pair',
        {'pairing_code': pairingCode}) as Map<String, dynamic>;
    return j;
  }

  /// 3) 查实例：elder_id + from/to，返回数组
  Future<List<Occurrence>> occurrences({required String elderId, DateTime? from, DateTime? to}) async {
    final today = DateTime.now();
    String d(DateTime x) => x.toIso8601String().substring(0, 10);
    final list = await _get('/api/v1/occurrences', {
      'elder_id': elderId,
      'from': d(from ?? today),
      'to': d(to ?? today),
    }) as List;
    return list.map((e) => Occurrence.fromJson(Map<String, dynamic>.from(e as Map))).toList();
  }

  /// App 端首页：一次拿全（后端聚合接口，等价于把 3 + 5 合成一次）
  Future<Bundle> fetchBundle() async {
    final j = await _get('/api/v1/app/bundle') as Map<String, dynamic>;
    final occ = (j['occurrences'] as List? ?? const [])
        .map((e) => Occurrence.fromJson(Map<String, dynamic>.from(e as Map)))
        .toList();
    return Bundle(
      plans: (j['plans'] as List? ?? const [])
          .map((e) => Plan.fromJson(Map<String, dynamic>.from(e as Map)))
          .toList(),
      due: (j['due'] as List? ?? const []).map((e) {
        final m = Map<String, dynamic>.from(e as Map);
        return DueItem(
          occurrenceId: m['id'].toString(),
          planId: m['plan_id'].toString(),
          title: m['title'].toString(),
          slotLocal: (m['slot_local'] ?? m['slot'] ?? '').toString(),
          lateMin: int.tryParse('${m['late_min']}') ?? 0,
          snoozeLeft: int.tryParse('${m['snooze_left']}') ?? 0,
        );
      }).toList(),
      occurrences: occ,
    );
  }

  /// 4) 提交事件：event_id 由客户端生成，client_ts 重试时保持不变
  Future<bool> pushEvent({
    required String occurrenceId,
    required String action,
    required String eventId,
    required String clientTs,
    String note = '',
  }) async {
    final j = await _send('POST', '/api/v1/occurrences/$occurrenceId/events', {
      'action': action,
      'event_id': eventId,
      'client_ts': clientTs,
      'note': note,
    }) as Map<String, dynamic>;
    // 契约 §5：duplicate=true 当成功处理
    return j['duplicate'] != true;
  }

  /// 5) 记录：at 用 ISO 8601 带时区
  Future<Map<String, dynamic>> addRecord({
    required String elderId,
    required String type,
    num? value,
    String unit = '',
    DateTime? at,
    String note = '',
  }) async {
    return await _send('POST', '/api/v1/records', {
      'elder_id': elderId,
      'type': type,
      'value': value,
      'unit': unit,
      'at': (at ?? DateTime.now()).toIso8601String(),
      'note': note,
    }) as Map<String, dynamic>;
  }

  /// 6) 统计：口径由后端算
  Future<Map<String, dynamic>> stats({required String elderId, String range = '7d'}) async {
    return await _get('/api/v1/stats', {'elder_id': elderId, 'range': range}) as Map<String, dynamic>;
  }

  /// 7) 告警：未确认超时的实例（数组）
  Future<List<Map<String, dynamic>>> alerts({required String elderId}) async {
    final list = await _get('/api/v1/alerts', {'elder_id': elderId}) as List;
    return list.map((e) => Map<String, dynamic>.from(e as Map)).toList();
  }

  Future<Map<String, dynamic>> me() async => await _get('/api/v1/me') as Map<String, dynamic>;
  // 函数 fetchStateSince：按游标回灌服务端状态（4.1 架构图第 5 层下行）
  Future<Map<String, dynamic>> fetchStateSince(String since) async {
    final j = await _get('/api/v1/state', {'since': since}) as Map<String, dynamic>;
    return j;
  }

  // 函数 pushEventsBatch：批量上行本地事件队列（4.1 架构图第 5 层上行）
  Future<Map<String, dynamic>> pushEventsBatch(List<Map<String, dynamic>> events) async {
    final j = await _send('POST', '/api/v1/events', {'events': events}) as Map<String, dynamic>;
    return j;
  }
}

