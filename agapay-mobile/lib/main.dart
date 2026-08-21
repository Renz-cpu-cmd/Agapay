import 'package:flutter/material.dart';
import 'core/theme/app_theme.dart';
import 'controllers/app_controller.dart';
import 'models/flood_alert.dart';
import 'navigation/app_routes.dart';
import 'navigation/main_navigation_shell.dart';
import 'screens/splash/splash_screen.dart';
import 'screens/auth/login_screen.dart';
import 'screens/auth/register_screen.dart';
import 'screens/dashboard/home_dashboard_screen.dart';
import 'screens/alert/alert_details_screen.dart';
import 'screens/water_level/water_level_details_screen.dart';
import 'screens/map/evacuation_map_screen.dart';
import 'screens/sos/sos_beacon_screen.dart';
import 'screens/station/station_map_screen.dart';
import 'screens/history/historical_charts_screen.dart';
import 'screens/notifications/notifications_inbox_screen.dart';
import 'screens/settings/settings_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  final appController = AppController();
  runApp(AgapayApp(controller: appController));
}

class AgapayApp extends StatelessWidget {
  final AppController controller;

  const AgapayApp({super.key, required this.controller});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'AGAPAY - Early Warning System',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.lightTheme,
      initialRoute: AppRoutes.splash,
      onGenerateRoute: (settings) {
        switch (settings.name) {
          case AppRoutes.splash:
            return MaterialPageRoute(builder: (_) => const SplashScreen());

          case AppRoutes.login:
            return MaterialPageRoute(builder: (_) => LoginScreen(controller: controller));

          case AppRoutes.register:
            return MaterialPageRoute(builder: (_) => RegisterScreen(controller: controller));

          case AppRoutes.home:
            return MaterialPageRoute(builder: (_) => MainNavigationShell(controller: controller));

          case AppRoutes.alertDetails:
            final alert = settings.arguments as FloodAlert? ?? controller.latestAlert;
            if (alert != null) {
              return MaterialPageRoute(builder: (_) => AlertDetailsScreen(alert: alert));
            }
            return MaterialPageRoute(builder: (_) => MainNavigationShell(controller: controller));

          case AppRoutes.waterLevelDetails:
            return MaterialPageRoute(builder: (_) => WaterLevelDetailsScreen(controller: controller));

          case AppRoutes.evacuationMap:
            return MaterialPageRoute(builder: (_) => EvacuationMapScreen(controller: controller));

          case AppRoutes.sosBeacon:
            return MaterialPageRoute(builder: (_) => SosBeaconScreen(controller: controller));

          case AppRoutes.stationMap:
            return MaterialPageRoute(builder: (_) => StationMapScreen(controller: controller));

          case AppRoutes.historicalCharts:
            return MaterialPageRoute(builder: (_) => HistoricalChartsScreen(controller: controller));

          case AppRoutes.notifications:
            return MaterialPageRoute(builder: (_) => NotificationsInboxScreen(controller: controller));

          case AppRoutes.settings:
            return MaterialPageRoute(builder: (_) => SettingsScreen(controller: controller));

          default:
            return MaterialPageRoute(builder: (_) => MainNavigationShell(controller: controller));
        }
      },
    );
  }
}
