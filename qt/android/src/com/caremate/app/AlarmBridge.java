// 作用：Java 侧：AlarmManager.setExactAndAllowWhileIdle + 通知渠道（普通/呼救两级）
// ------------------------------------------------------------------
// Java 侧：精确闹钟 + 通知（报告 §3.2 B4 里点名的"30–60 行 Java"）
// 放到 app-qt/android/src/com/caremate/app/AlarmBridge.java
// ------------------------------------------------------------------
package com.caremate.app;

import android.app.Activity;
import android.app.AlarmManager;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.provider.Settings;
import androidx.core.app.NotificationCompat;

public final class AlarmBridge {
    private static final String CHANNEL = "caremate-reminder";
    private static final String CHANNEL_SOS = "caremate-sos";

    private AlarmBridge() {}

    /** 两个渠道：普通提醒走 CHANNEL，呼救走 CHANNEL_SOS（声音更大、绕过免打扰） */
    public static void ensureChannel(Context ctx) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return;
        NotificationManager nm = ctx.getSystemService(NotificationManager.class);
        NotificationChannel normal = new NotificationChannel(
                CHANNEL, "用药与作息提醒", NotificationManager.IMPORTANCE_HIGH);
        normal.setSound(null, null);                 // 声音由 Qt 侧的 TTS 负责，避免双重响
        nm.createNotificationChannel(normal);

        NotificationChannel sos = new NotificationChannel(
                CHANNEL_SOS, "呼救", NotificationManager.IMPORTANCE_MAX);
        sos.setBypassDnd(true);
        nm.createNotificationChannel(sos);
    }

    public static boolean canScheduleExact(Context ctx) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.S) return true;
        AlarmManager am = (AlarmManager) ctx.getSystemService(Context.ALARM_SERVICE);
        return am != null && am.canScheduleExactAlarms();
    }

    public static void schedule(Context ctx, String id, long triggerAtMillis,
                                String title, String body) {
        AlarmManager am = (AlarmManager) ctx.getSystemService(Context.ALARM_SERVICE);
        if (am == null) return;
        PendingIntent pi = pending(ctx, id, title, body);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            // 关键：setExactAndAllowWhileIdle，Doze 下也能准时；周期小于 9 分钟会被系统拉长
            am.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, triggerAtMillis, pi);
        } else {
            am.setExact(AlarmManager.RTC_WAKEUP, triggerAtMillis, pi);
        }
    }

    public static void cancel(Context ctx, String id) {
        AlarmManager am = (AlarmManager) ctx.getSystemService(Context.ALARM_SERVICE);
        if (am != null) am.cancel(pending(ctx, id, "", ""));
    }

    /** 引导用户开"精确闹钟"权限（root 机器上改用 android-root 脚本直接授权） */
    public static void requestPermissions(Activity activity) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S && !canScheduleExact(activity)) {
            Intent i = new Intent(Settings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM,
                    Uri.parse("package:" + activity.getPackageName()));
            activity.startActivity(i);
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            activity.requestPermissions(new String[]{"android.permission.POST_NOTIFICATIONS"}, 1001);
        }
    }

    private static PendingIntent pending(Context ctx, String id, String title, String body) {
        Intent i = new Intent(ctx, ReminderReceiver.class)
                .putExtra("id", id).putExtra("title", title).putExtra("body", body);
        int flags = PendingIntent.FLAG_UPDATE_CURRENT;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) flags |= PendingIntent.FLAG_IMMUTABLE;
        return PendingIntent.getBroadcast(ctx, id.hashCode(), i, flags);
    }
}
