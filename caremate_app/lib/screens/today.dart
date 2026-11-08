// 作用：今天页：到点卡片 + 吃了/等会儿/没做 三个大按钮
import 'package:flutter/material.dart';

import '../models.dart';
import '../state.dart';

/// 老人端「今天」——定量标准见 4.1：正文 24、标题 42、主按钮 84 高、单屏 3 个选项
const double kBody = 24;
const double kTitle = 42;
const double kTap = 84;
const Color kInk = Color(0xFF14264A);

class TodayPage extends StatelessWidget {
  const TodayPage({super.key, required this.state});
  final AppState state;

  @override
  // 函数 build：今天页布局：到点卡片 + 三个大按钮 + 今日列表
  Widget build(BuildContext context) {
    final due = state.due;
    final today = state.todayEvents();

    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 32),
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              TimeOfDay.now().format(context),
              style: const TextStyle(fontSize: 44, fontWeight: FontWeight.w700, color: kInk),
            ),
            Text(
              state.syncing ? '同步中…' : (state.lastSyncAt == null ? '离线可用' : '已同步 ${state.lastSyncAt}'),
              style: const TextStyle(fontSize: 14, color: Color(0xFF3A4A63)),
            ),
          ],
        ),
        const SizedBox(height: 18),
        if (due.isEmpty) _idleCard() else _reminderCard(due.first),
        const SizedBox(height: 26),
        const Text('今天的计划', style: TextStyle(fontSize: 28, fontWeight: FontWeight.w700, color: kInk)),
        const SizedBox(height: 8),
        ...state.plans.expand((p) => p.timesToday().map((t) => _planRow(p.title, t, p.dose))),
        const SizedBox(height: 20),
        const Text('今天的记录', style: TextStyle(fontSize: 28, fontWeight: FontWeight.w700, color: kInk)),
        const SizedBox(height: 8),
        if (today.isEmpty)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 12),
            child: Text('还没有记录', style: TextStyle(fontSize: kBody, color: Color(0xFF3A4A63))),
          )
        else
          ...today.map((e) => _eventRow(e)),
        const SizedBox(height: 20),
        if (state.lastError != null)
          Text(state.lastError!, style: const TextStyle(color: Color(0xFF7E1B22), fontSize: 16)),
      ],
    );
  }

  Widget _idleCard() => Container(
        padding: const EdgeInsets.symmetric(vertical: 40, horizontal: 18),
        decoration: BoxDecoration(
          border: Border.all(color: const Color(0xFFCBD7E8), width: 3),
          borderRadius: BorderRadius.circular(20),
        ),
        alignment: Alignment.center,
        child: const Column(
          children: [
            Text('现在没有要做的事', style: TextStyle(fontSize: 30, fontWeight: FontWeight.w700, color: kInk)),
            SizedBox(height: 6),
            Text('到点会自动提醒你', style: TextStyle(fontSize: kBody, color: Color(0xFF3A4A63))),
          ],
        ),
      );

  // 函数 _reminderCard：到点卡片：标题、计划时间、迟到分钟
  Widget _reminderCard(DueItem item) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: const Color(0xFFEEF4FC),
        border: Border.all(color: const Color(0xFF9DB4D4), width: 3),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('现在该做的事', style: TextStyle(fontSize: kBody, color: Color(0xFF3A4A63))),
          const SizedBox(height: 6),
          Text(item.title, style: const TextStyle(fontSize: kTitle, fontWeight: FontWeight.w700, color: kInk)),
          const SizedBox(height: 4),
          Text('计划时间 ${item.slotLocal.length > 11 ? item.slotLocal.substring(11) : item.slotLocal}',
              style: const TextStyle(fontSize: kBody, color: Color(0xFF3A4A63))),
          if (item.lateMin > 0)
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Text('已经过了 ${item.lateMin} 分钟',
                  style: const TextStyle(fontSize: kBody, fontWeight: FontWeight.w700, color: Color(0xFF6E3F05))),
            ),
          const SizedBox(height: 18),
          _bigButton('吃了，记一下', filled: true, onTap: () => _record(item, 'confirmed')),
          const SizedBox(height: 12),
          _bigButton('等会儿再做', filled: false, onTap: () => _record(item, 'snoozed')),
          const SizedBox(height: 12),
          _dangerButton('这次没做', onTap: () => _record(item, 'missed')),
        ],
      ),
    );
  }

  // 函数 _bigButton：主操作按钮（吃了/等会儿），84 高、30 号字
  Widget _bigButton(String text, {bool filled = true, required VoidCallback onTap}) {
    return SizedBox(
      width: double.infinity,
      height: kTap,
      child: FilledButton(
        style: FilledButton.styleFrom(
          backgroundColor: filled ? const Color(0xFF24457A) : Colors.white,
          foregroundColor: filled ? Colors.white : const Color(0xFF24457A),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
            side: const BorderSide(color: Color(0xFF24457A), width: 3),
          ),
        ),
        onPressed: onTap,
        child: Text(text, style: const TextStyle(fontSize: 30, fontWeight: FontWeight.w700)),
      ),
    );
  }

  // 函数 _dangerButton：次要操作按钮（这次没做），红框，弱化视觉
  Widget _dangerButton(String text, {required VoidCallback onTap}) {
    return SizedBox(
      width: double.infinity,
      height: 72,
      child: OutlinedButton(
        style: OutlinedButton.styleFrom(
          foregroundColor: const Color(0xFF7E1B22),
          side: const BorderSide(color: Color(0xFF7E1B22), width: 3),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        ),
        onPressed: onTap,
        child: Text(text, style: const TextStyle(fontSize: 26, fontWeight: FontWeight.w700)),
      ),
    );
  }

  /// 契约 §4：客户端只把动作作为事件提交，状态等云端回来再刷新
  Future<void> _record(DueItem item, String action) async {
    final occ = state.occurrences.where((o) => o.id == item.occurrenceId).toList();
    if (occ.isEmpty) return;
    await state.record(occ.first, action);
    await state.sync();
  }

  Widget _planRow(String title, String time, String dose) => Container(
        padding: const EdgeInsets.symmetric(vertical: 12),
        decoration: const BoxDecoration(border: Border(bottom: BorderSide(color: Color(0xFFE8EEF7), width: 2))),
        child: Row(
          children: [
            SizedBox(
              width: 80,
              child: Text(time, style: const TextStyle(fontSize: kBody, color: Color(0xFF3A4A63))),
            ),
            Expanded(
              child: Text('$title${dose.isNotEmpty ? " · $dose" : ""}',
                  style: const TextStyle(fontSize: kBody, fontWeight: FontWeight.w600, color: kInk)),
            ),
          ],
        ),
      );

  // 函数 _eventRow：动作流水行：标题 + 状态 + 未同步标记
  Widget _eventRow(AppEvent e) {
    final color = switch (e.action) {
      'confirmed' => const Color(0xFF0E5B33),
      'snoozed' => const Color(0xFF6E3F05),
      _ => const Color(0xFF7E1B22),
    };
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 12),
      decoration: const BoxDecoration(border: Border(bottom: BorderSide(color: Color(0xFFE8EEF7), width: 2))),
      child: Row(
        children: [
          SizedBox(
            width: 96,
            child: Text(e.statusLabel, style: TextStyle(fontWeight: FontWeight.w700, color: color, fontSize: kBody)),
          ),
          SizedBox(
            width: 64,
            child: Text(e.slotLocal.length > 11 ? e.slotLocal.substring(11) : e.slotLocal,
                style: const TextStyle(fontSize: kBody)),
          ),
          Expanded(child: Text(e.title, style: const TextStyle(fontSize: kBody, color: Color(0xFF3A4A63)))),
          if (!e.synced) const Icon(Icons.cloud_off, size: 18, color: Colors.orangeAccent),
        ],
      ),
    );
  }
}
