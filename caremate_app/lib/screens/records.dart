import 'package:flutter/material.dart';

import '../state.dart';

/// 记录：近 7 天统计 + 流水
class RecordsPage extends StatelessWidget {
  const RecordsPage({super.key, required this.state});
  final AppState state;

  @override
  Widget build(BuildContext context) {
    final s = state.weeklyStats();
    final rate = s['rate']!;

    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 32),
      children: [
        const Text('近 7 天', style: TextStyle(fontSize: 22, fontWeight: FontWeight.w700)),
        const SizedBox(height: 14),
        Row(
          children: [
            _card('事件', '${s['total']}'),
            const SizedBox(width: 10),
            _card('已确认', '${s['confirmed']}'),
            const SizedBox(width: 10),
            _card('未确认', '${s['missed']}'),
            const SizedBox(width: 10),
            _card('确认率', rate < 0 ? '—' : '$rate%'),
          ],
        ),
        const SizedBox(height: 26),
        const Text('事件流水', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
        const SizedBox(height: 8),
        if (state.events.isEmpty)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 16),
            child: Text('还没有事件', style: TextStyle(color: Colors.blueGrey)),
          )
        else
          ...state.events.take(60).map((e) {
            final color = switch (e.status) {
              'confirmed' => const Color(0xFF1F7A4D),
              'snoozed' => const Color(0xFFA8620A),
              _ => const Color(0xFFA3282F),
            };
            return Container(
              padding: const EdgeInsets.symmetric(vertical: 11),
              decoration: const BoxDecoration(
                border: Border(bottom: BorderSide(color: Color(0xFFE6ECF4))),
              ),
              child: Row(
                children: [
                  Expanded(child: Text(e.slot, style: const TextStyle(fontSize: 14))),
                  Expanded(flex: 2, child: Text(e.title, style: const TextStyle(fontSize: 14))),
                  Text(e.statusLabel,
                      style: TextStyle(fontWeight: FontWeight.w700, color: color, fontSize: 14)),
                ],
              ),
            );
          }),
        const SizedBox(height: 20),
        const Text(
          '未同步的记录会在联网后自动补传；同一时刻不会出现两条记录。',
          style: TextStyle(fontSize: 12, color: Colors.blueGrey),
        ),
      ],
    );
  }

  Widget _card(String k, String v) => Expanded(
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 12),
          decoration: BoxDecoration(
            color: Colors.white,
            border: Border.all(color: const Color(0xFFE1E8F3)),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(k, style: const TextStyle(fontSize: 12, color: Colors.blueGrey)),
              const SizedBox(height: 4),
              Text(v, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w700)),
            ],
          ),
        ),
      );
}
