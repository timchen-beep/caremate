// 作用：端上 30 秒 tick（4.1 架构图第 3 层）：到点把本地实例置 notified 并触发本机通知；升级与告警仍由云端兜底
import 'dart:async';

import 'local_db.dart';
import 'models.dart';
import 'notify.dart';

/// 端上调度器。
///
/// 与云端的职责划分（方案 B）：
/// - 端上：到点即 notified + 本机通知（不依赖网络）
/// - 云端：escalated（2 分钟通知家属）与 missed（15 分钟）由服务端 scheduler 兜底
class DeviceScheduler {
  DeviceScheduler({this.onChanged});

  final void Function()? onChanged;
  Timer? _timer;
  int _nextId = 5000;

  void start() {
    _timer ??= Timer.periodic(const Duration(seconds: 30), (_) => tick());
    tick();
  }

  void stop() {
    _timer?.cancel();
    _timer = null;
  }

  /// 一次扫描：把已到期、仍为 pending 的本地实例转成 notified，并弹本机通知
  Future<void> tick() async {
    final today = dateOf(DateTime.now());
    final list = await LocalDb.occurrencesForDate(today);
    final now = DateTime.now();
    var changed = 0;
    for (final o in list) {
      if (o.state != 'pending') continue;
      final due = DateTime.tryParse(o.slotLocal.replaceFirst(' ', 'T'));
      if (due == null || due.isAfter(now)) continue;
      final at = DateTime.now().toUtc().toIso8601String();
      changed += await LocalDb.markNotified(o.id, at);
      await Notifier.showReminder(
        _nextId++,
        o.title.isEmpty ? '该做这件事了' : o.title,
        '${o.slotLocal.length > 11 ? o.slotLocal.substring(11) : o.slotLocal} 的提醒 · 点开确认一下',
      );
    }
    if (changed > 0) onChanged?.call();
  }
}