// 作用：本地通知：通知渠道、按计划重排精确闹钟（setExactAndAllowWhileIdle）、开机重排
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:timezone/data/latest_all.dart' as tzdata;
import 'package:timezone/timezone.dart' as tz;

import 'models.dart';

/// 本地通知：这是"App 当终端"的核心——不依赖网络，到点必响。
class Notifier {
  static final FlutterLocalNotificationsPlugin _plugin = FlutterLocalNotificationsPlugin();
  static const String _channelId = 'caremate_reminders';
  static const String _channelName = '用药与作息提醒';

  /// App 启动时调用一次
  static Future<void> init() async {
    tzdata.initializeTimeZones();
    try {
      tz.setLocalLocation(tz.getLocation('Asia/Shanghai'));
    } catch (_) {
      // 设备缺少时区库时退回 UTC，仅影响跨时区场景
    }

    const android = AndroidInitializationSettings('@mipmap/ic_launcher');
    const ios = DarwinInitializationSettings(
      requestAlertPermission: true,
      requestBadgePermission: true,
      requestSoundPermission: true,
    );

    await _plugin.initialize(
      const InitializationSettings(android: android, iOS: ios),
      onDidReceiveNotificationResponse: (resp) {
        // 点通知进入 App：由 UI 层读取 payload 定位到那条待办
        lastTappedPlanId = resp.payload;
      },
    );

    // Android 13+ 通知权限；Android 12+ 精确闹钟权限
    final androidImpl = _plugin.resolvePlatformSpecificImplementation<
        AndroidFlutterLocalNotificationsPlugin>();
    await androidImpl?.requestNotificationsPermission();
    await androidImpl?.requestExactAlarmsPermission();

    final iosImpl =
        _plugin.resolvePlatformSpecificImplementation<IOSFlutterLocalNotificationsPlugin>();
    await iosImpl?.requestPermissions(alert: true, badge: true, sound: true);
  }

  /// 点通知带出来的计划 ID
  static String? lastTappedPlanId;

  static tz.TZDateTime _nextInstanceOf(int hour, int minute) {
    final now = tz.TZDateTime.now(tz.local);
    var scheduled = tz.TZDateTime(tz.local, now.year, now.month, now.day, hour, minute);
    if (scheduled.isBefore(now)) {
      scheduled = scheduled.add(const Duration(days: 1));
    }
    return scheduled;
  }

  /// 按计划重建全部提醒（每天重复）
  static Future<void> rescheduleAll(List<Plan> plans, {List<DueItem> due = const []}) async {
    await _plugin.cancelAll();
    var id = 1;
    for (final p in plans) {
      if (!p.active) continue;
      for (final t in p.times) {
        final parts = t.split(':');
        if (parts.length != 2) continue;
        final hh = int.tryParse(parts[0]) ?? -1;
        final mm = int.tryParse(parts[1]) ?? -1;
        if (hh < 0 || hh > 23 || mm < 0 || mm > 59) continue;
        await _plugin.zonedSchedule(
          id++,
          p.title,
          '${t.substring(0, 5)} 的提醒 · 点开后请确认是否已完成',
          _nextInstanceOf(hh, mm),
          const NotificationDetails(
            android: AndroidNotificationDetails(
              _channelId,
              _channelName,
              channelDescription: '按计划提醒用药、饮水与活动',
              importance: Importance.max,
              priority: Priority.high,
              category: AndroidNotificationCategory.reminder,
              fullScreenIntent: true,
              playSound: true,
            ),
            iOS: DarwinNotificationDetails(
              presentAlert: true,
              presentSound: true,
              interruptionLevel: InterruptionLevel.timeSensitive,
            ),
          ),
          androidScheduleMode: AndroidScheduleMode.exactAllowWhileIdle,
          uiLocalNotificationDateInterpretation:
              UILocalNotificationDateInterpretation.absoluteTime,
          matchDateTimeComponents: DateTimeComponents.time,
          payload: p.id,
        );
      }
    }
  }

  // 函数 showReminder：端上调度器到点时弹一条提醒（不依赖服务器）
  static Future<void> showReminder(int id, String title, String body) async {
    await _plugin.show(
      id,
      title,
      body,
      const NotificationDetails(
        android: AndroidNotificationDetails(
          _channelId,
          _channelName,
          channelDescription: '按计划提醒用药、饮水与活动',
          importance: Importance.max,
          priority: Priority.high,
          category: AndroidNotificationCategory.reminder,
          fullScreenIntent: true,
        ),
        iOS: DarwinNotificationDetails(presentAlert: true, presentSound: true),
      ),
    );
  }
  /// 设置页的"测试通知"
  static Future<void> showTest() async {
    await _plugin.show(
      9999,
      '测试提醒',
      '如果你看到这条通知，说明通知权限没问题',
      const NotificationDetails(
        android: AndroidNotificationDetails(
          _channelId,
          _channelName,
          importance: Importance.max,
          priority: Priority.high,
        ),
        iOS: DarwinNotificationDetails(presentAlert: true, presentSound: true),
      ),
    );
  }
}

