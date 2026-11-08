// 作用：记录页：今日统计、今天要做的事、已提交动作（含未同步标记）
import 'package:flutter/material.dart';

import '../state.dart';

/// 记录：今日统计 + 今天要做的事 + 已提交的动作
/// 统计口径以服务端 /api/v1/stats 为准，这里只做本地展示兜底。
class RecordsPage extends StatelessWidget {
  const RecordsPage({super.key, required this.state});
  final AppState state;

  @override
  // 函数 build：记录页：今日统计 + 今天要做的事 + 已提交动作
  Widget build(BuildContext context) {
    final total = state.occurrences.length;
    final done = state.occurrences.where((o) => o.state == 'confirmed').length;
    final miss = state.occurrences.where((o) => o.state == 'missed').length;
    final rate = total == 0 ? -1 : ((done / total) * 100).round();

    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 32),
      children: [
        const Text('今天', style: TextStyle(fontSize: 26, fontWeight: FontWeight.w700)),
        const SizedBox(height: 12),
        Row(
          children: [
            _card('实例', '$total'),
            const SizedBox(width: 8),
            _card('已确认', '$done'),
            const SizedBox(width: 8),
            _card('未确认', '$miss'),
            const SizedBox(width: 8),
            _card('确认率', rate < 0 ? '—' : '$rate%'),
          ],
        ),
        const SizedBox(height: 24),
        const Text('今天要做的', style: TextStyle(fontSize: 26, fontWeight: FontWeight.w700)),
        const SizedBox(height: 8),
        if (state.occurrences.isEmpty)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 16),
            child: Text('今天没有计划', style: TextStyle(fontSize: 18, color: Color(0xFF3A4A63))),
          )
        else
          ...state.occurrences.map((o) {
            final color = switch (o.state) {
              'confirmed' => const Color(0xFF0E5B33),
              'missed' => const Color(0xFF7E1B22),
              _ => const Color(0xFF3A4A63),
            };
            return Container(
              padding: const EdgeInsets.symmetric(vertical: 12),
              decoration: const BoxDecoration(
                border: Border(bottom: BorderSide(color: Color(0xFFE8EEF7), width: 2)),
              ),
              child: Row(
                children: [
                  SizedBox(
                    width: 72,
                    child: Text(
                        o.slotLocal.length > 11 ? o.slotLocal.substring(11) : o.slotLocal,
                        style: const TextStyle(fontSize: 18)),
                  ),
                  Expanded(
                    child: Text(o.title,
                        style: const TextStyle(fontSize: 19, fontWeight: FontWeight.w600)),
                  ),
                  Text(o.stateLabel,
                      style: TextStyle(fontWeight: FontWeight.w700, color: color, fontSize: 18)),
                ],
              ),
            );
          }),
        const SizedBox(height: 22),
        const Text('已提交的动作', style: TextStyle(fontSize: 26, fontWeight: FontWeight.w700)),
        const SizedBox(height: 8),
        if (state.events.isEmpty)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 12),
            child: Text('还没有动作', style: TextStyle(fontSize: 18, color: Color(0xFF3A4A63))),
          )
        else
          ...state.events.take(30).map((e) {
            final color = switch (e.action) {
              'confirmed' => const Color(0xFF0E5B33),
              'snoozed' => const Color(0xFF6E3F05),
              _ => const Color(0xFF7E1B22),
            };
            return Container(
              padding: const EdgeInsets.symmetric(vertical: 12),
              decoration: const BoxDecoration(
                border: Border(bottom: BorderSide(color: Color(0xFFE8EEF7), width: 2)),
              ),
              child: Row(
                children: [
                  Expanded(child: Text(e.title, style: const TextStyle(fontSize: 18))),
                  if (!e.synced)
                    const Icon(Icons.cloud_off, size: 18, color: Colors.orangeAccent),
                  const SizedBox(width: 6),
                  Text(e.statusLabel,
                      style: TextStyle(fontWeight: FontWeight.w700, color: color, fontSize: 18)),
                ],
              ),
            );
          }),
        const SizedBox(height: 18),
        const Text(
          '没联网时动作会先排队，联网后按原样重发；服务端靠 event_id 去重，不会出现两条。',
          style: TextStyle(fontSize: 15, color: Color(0xFF3A4A63)),
        ),
      ],
    );
  }

  Widget _card(String k, String v) => Expanded(
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 10),
          decoration: BoxDecoration(
            color: Colors.white,
            border: Border.all(color: const Color(0xFFE1E8F3), width: 2),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(k, style: const TextStyle(fontSize: 15, color: Color(0xFF3A4A63))),
              const SizedBox(height: 4),
              Text(v, style: const TextStyle(fontSize: 26, fontWeight: FontWeight.w700)),
            ],
          ),
        ),
      );
}
