// 作用：我的页：服务器地址与令牌、配对码、通知自检、同步状态
import 'package:flutter/material.dart';

import '../notify.dart';
import '../state.dart';

/// 我的：服务器、令牌、绑定码、通知与同步
class SettingsPage extends StatefulWidget {
  const SettingsPage({super.key, required this.state});
  final AppState state;

  @override
  State<SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends State<SettingsPage> {
  late final TextEditingController _url;
  late final TextEditingController _token;
  String _tip = '';
  String _bindCode = '——';

  @override
  // 函数 initState：读取已保存的服务器地址与令牌
  void initState() {
    super.initState();
    _url = TextEditingController(text: widget.state.baseUrl);
    _token = TextEditingController(text: widget.state.token);
    _loadMe();
  }

  // 函数 _loadMe：拉取当前账号信息（角色、绑定老人）
  Future<void> _loadMe() async {
    try {
      final me = await widget.state.api.me();
      final code = me['bind_code']?.toString() ?? '——';
      if (mounted) setState(() => _bindCode = code);
    } catch (_) {
      /* 离线时保持占位符 */
    }
  }

  @override
  // 函数 dispose：释放输入框控制器
  void dispose() {
    _url.dispose();
    _token.dispose();
    super.dispose();
  }

  @override
  // 函数 build：我的页布局：服务器/令牌、配对、通知自检、同步状态
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 32),
      children: [
        const Text('我的', style: TextStyle(fontSize: 22, fontWeight: FontWeight.w700)),
        const SizedBox(height: 18),
        _label('云端地址'),
        TextField(
          controller: _url,
          decoration: const InputDecoration(
            border: OutlineInputBorder(),
            hintText: 'http://192.168.1.10:8000',
            helperText: '模拟器用 10.0.2.2，真机用电脑局域网 IP',
          ),
        ),
        const SizedBox(height: 14),
        _label('设备令牌'),
        TextField(
          controller: _token,
          decoration: const InputDecoration(
            border: OutlineInputBorder(),
            hintText: 'app-elder-001',
          ),
        ),
        const SizedBox(height: 12),
        Row(
          children: [
            FilledButton(
              onPressed: () async {
                await widget.state.saveSettings(url: _url.text, tk: _token.text);
                setState(() => _tip = '已保存，正在同步…');
                await widget.state.sync();
                setState(() => _tip = widget.state.lastError ?? '同步完成');
              },
              child: const Text('保存并同步'),
            ),
            const SizedBox(width: 12),
            OutlinedButton(
              onPressed: () async {
                await Notifier.showTest();
                setState(() => _tip = '已发送测试通知（没看到就看系统通知权限）');
              },
              child: const Text('测试通知'),
            ),
          ],
        ),
        if (_tip.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 10),
            child: Text(_tip, style: const TextStyle(fontSize: 13, color: Colors.blueGrey)),
          ),
        const SizedBox(height: 26),
        _label('绑定码（家属在 Web 端填这个码来关联）'),
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: Colors.white,
            border: Border.all(color: const Color(0xFFE1E8F3)),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(_bindCode, style: const TextStyle(fontSize: 30, fontWeight: FontWeight.w700, letterSpacing: 6)),
              Text(widget.state.userId, style: const TextStyle(fontSize: 12, color: Colors.blueGrey)),
            ],
          ),
        ),
        const SizedBox(height: 26),
        _label('提醒能力自检'),
        const Text(
          '· 通知权限：Android 13 及以上需在系统设置里允许\n'
          '· 精确闹钟：Android 12 及以上需允许「闹钟和提醒」\n'
          '· 后台保活：部分国产系统需把本应用加入自启动/后台白名单\n'
          '· 断网时仍会按本地缓存的时间提醒，记录联网后补传',
          style: TextStyle(fontSize: 13, height: 1.7, color: Colors.blueGrey),
        ),
        const SizedBox(height: 26),
        OutlinedButton(
          style: OutlinedButton.styleFrom(foregroundColor: const Color(0xFFA3282F)),
          onPressed: () async {
            await widget.state.sync();
            if (mounted) setState(() => _tip = widget.state.lastError ?? '已刷新');
          },
          child: const Text('立即刷新云端数据'),
        ),
      ],
    );
  }

  Widget _label(String text) => Padding(
        padding: const EdgeInsets.only(bottom: 6),
        child: Text(text, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
      );
}

// 文件：caremate_app/lib/screens/settings.dart
