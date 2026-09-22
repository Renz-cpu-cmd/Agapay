import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'controllers/app_controller.dart';
import 'core/theme/app_theme.dart';
import 'navigation/app_routes.dart';
import 'navigation/main_navigation_shell.dart';
import 'screens/alerts/notification_history_screen.dart';
import 'screens/auth/login_screen.dart';
import 'screens/auth/register_screen.dart';
import 'screens/splash/splash_screen.dart';

class AgapayApp extends StatefulWidget {
  const AgapayApp({this.controller, super.key});
  final AppController? controller;
  @override
  State<AgapayApp> createState() => _AgapayAppState();
}

class _AgapayAppState extends State<AgapayApp> {
  late final _controller = widget.controller ?? AppController();
  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AppScope(
    controller: _controller,
    child: MaterialApp(
      title: 'AGAPAY',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.dark,
      initialRoute: AppRoutes.splash,
      builder: (context, child) => AnnotatedRegion<SystemUiOverlayStyle>(
        value: const SystemUiOverlayStyle(
          statusBarColor: Colors.transparent,
          statusBarIconBrightness: Brightness.light,
          statusBarBrightness: Brightness.dark,
          systemNavigationBarColor: AppColors.background,
          systemNavigationBarIconBrightness: Brightness.light,
        ),
        child: ColoredBox(
          color: const Color(0xff020508),
          child: LayoutBuilder(
            builder: (context, box) => Center(
              child: SizedBox(
                width: box.maxWidth >= 600 ? 390 : box.maxWidth,
                child: ScrollConfiguration(
                  behavior: ScrollConfiguration.of(
                    context,
                  ).copyWith(scrollbars: false),
                  child: child!,
                ),
              ),
            ),
          ),
        ),
      ),
      routes: {
        AppRoutes.splash: (_) => const SplashScreen(),
        AppRoutes.login: (_) => const LoginScreen(),
        AppRoutes.register: (_) => const RegisterScreen(),
        AppRoutes.main: (_) => const _AccountGate(child: MainNavigationShell()),
        AppRoutes.notificationHistory: (_) =>
            const _AccountGate(child: NotificationHistoryScreen()),
      },
    ),
  );
}

class _AccountGate extends StatelessWidget {
  const _AccountGate({required this.child});
  final Widget child;
  @override
  Widget build(BuildContext context) =>
      AppScope.of(context).signedIn ? child : const LoginScreen();
}
