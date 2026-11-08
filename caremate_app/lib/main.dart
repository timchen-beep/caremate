// 作用：App 入口：初始化状态与本地通知，挂三个 tab（今天/记录/我的）
import 'package:flutter/material.dart';

import 'notify.dart';
import 'screens/records.dart';
import 'screens/settings.dart';
import 'screens/today.dart';
import 'state.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final state = AppState();
  await state.init();
  await Notifier.init();
  await Notifier.rescheduleAll(state.plans, due: state.due);
  runApp(CareMateApp(state: state));
}

class CareMateApp extends StatelessWidget {
  const CareMateApp({super.key, required this.state});
  final AppState state;

  @override
  // 函数 build：构建界面（App 外层 / 首页外壳）
  Widget build(BuildContext context) {
    const ink = Color(0xFF14264A);
    const accent = Color(0xFF24457A);

    return MaterialApp(
      title: 'CareMate',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(seedColor: accent, primary: accent),
        scaffoldBackgroundColor: const Color(0xFFF6F8FC),
        // 老人端统一大字：正文 24、标题 26，避免各处硬编码
        textTheme: const TextTheme(
          bodyMedium: TextStyle(fontSize: 24, height: 1.4, color: ink),
          bodySmall: TextStyle(fontSize: 16, color: Color(0xFF3A4A63)),
          titleLarge: TextStyle(fontSize: 26, fontWeight: FontWeight.w700, color: ink),
        ),
        appBarTheme: const AppBarTheme(
          backgroundColor: Colors.white,
          foregroundColor: ink,
          elevation: 0,
          centerTitle: false,
        ),
      ),
      home: RootPage(state: state),
    );
  }
}

class RootPage extends StatefulWidget {
  const RootPage({super.key, required this.state});
  final AppState state;

  @override
  State<RootPage> createState() => _RootPageState();
}

class _RootPageState extends State<RootPage> with WidgetsBindingObserver {
  int _index = 0;

  @override
  // 函数 initState：启动时初始化状态与本地通知
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  // 函数 dispose：释放控制器与计时器
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // 回到前台：重新算待办、补同步、重建通知
    if (state == AppLifecycleState.resumed) {
      widget.state.recomputeDue();
      widget.state.pushPending();
      widget.state.sync();
      Notifier.rescheduleAll(widget.state.plans, due: widget.state.due);
    }
  }

  @override
  // 函数 build：构建界面（App 外层 / 首页外壳）
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: widget.state,
      builder: (context, _) {
        final pages = [
          TodayPage(state: widget.state),
          RecordsPage(state: widget.state),
          SettingsPage(state: widget.state),
        ];
        return Scaffold(
          body: SafeArea(child: IndexedStack(index: _index, children: pages)),
          bottomNavigationBar: NavigationBar(
            selectedIndex: _index,
            onDestinationSelected: (i) => setState(() => _index = i),
            destinations: const [
              NavigationDestination(icon: Icon(Icons.notifications_active_outlined), label: '今天'),
              NavigationDestination(icon: Icon(Icons.event_note_outlined), label: '记录'),
              NavigationDestination(icon: Icon(Icons.settings_outlined), label: '我的'),
            ],
          ),
        );
      },
    );
  }
}

