import 'package:flutter/material.dart';
import '../core/theme/app_colors.dart';
import '../controllers/app_controller.dart';
import '../screens/dashboard/home_dashboard_screen.dart';
import '../screens/map/evacuation_map_screen.dart';
import '../screens/notifications/notifications_inbox_screen.dart';
import '../screens/settings/settings_screen.dart';
import 'app_routes.dart';

/// Main Application Shell hosting the 4-tab Bottom Navigation and Global SOS shortcut
class MainNavigationShell extends StatefulWidget {
  final AppController controller;

  const MainNavigationShell({super.key, required this.controller});

  @override
  State<MainNavigationShell> createState() => _MainNavigationShellState();
}

class _MainNavigationShellState extends State<MainNavigationShell> {
  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: widget.controller,
      builder: (context, _) {
        final currentIndex = widget.controller.currentTabIndex;

        final screens = [
          HomeDashboardScreen(controller: widget.controller),
          EvacuationMapScreen(controller: widget.controller),
          NotificationsInboxScreen(controller: widget.controller),
          SettingsScreen(controller: widget.controller),
        ];

        return Scaffold(
          body: IndexedStack(
            index: currentIndex,
            children: screens,
          ),
          bottomNavigationBar: Container(
            decoration: const BoxDecoration(
              border: Border(top: BorderSide(color: AppColors.border, width: 1.0)),
            ),
            child: BottomNavigationBar(
              currentIndex: currentIndex,
              onTap: (index) => widget.controller.setTabIndex(index),
              type: BottomNavigationBarType.fixed,
              backgroundColor: Colors.white,
              selectedItemColor: AppColors.primary,
              unselectedItemColor: AppColors.textMuted,
              selectedLabelStyle: const TextStyle(fontWeight: FontWeight.w700, fontSize: 11),
              unselectedLabelStyle: const TextStyle(fontWeight: FontWeight.w500, fontSize: 11),
              items: [
                const BottomNavigationBarItem(
                  icon: Icon(Icons.home_rounded),
                  activeIcon: Icon(Icons.home_rounded),
                  label: 'Home',
                ),
                const BottomNavigationBarItem(
                  icon: Icon(Icons.map_outlined),
                  activeIcon: Icon(Icons.map_rounded),
                  label: 'Map',
                ),
                BottomNavigationBarItem(
                  icon: Stack(
                    clipBehavior: Clip.none,
                    children: [
                      const Icon(Icons.notifications_outlined),
                      if (widget.controller.unreadNotificationCount > 0)
                        Positioned(
                          right: -4,
                          top: -2,
                          child: Container(
                            width: 8,
                            height: 8,
                            decoration: const BoxDecoration(
                              color: AppColors.alertEvacuate,
                              shape: BoxShape.circle,
                            ),
                          ),
                        ),
                    ],
                  ),
                  activeIcon: const Icon(Icons.notifications_rounded),
                  label: 'Alerts',
                ),
                const BottomNavigationBarItem(
                  icon: Icon(Icons.settings_outlined),
                  activeIcon: Icon(Icons.settings_rounded),
                  label: 'Settings',
                ),
              ],
            ),
          ),
          floatingActionButton: FloatingActionButton.extended(
            onPressed: () {
              Navigator.pushNamed(context, AppRoutes.sosBeacon);
            },
            backgroundColor: AppColors.sosRed,
            foregroundColor: Colors.white,
            elevation: 4,
            icon: const Icon(Icons.emergency_rounded, size: 20),
            label: const Text(
              'SOS',
              style: TextStyle(fontWeight: FontWeight.w900, letterSpacing: 1.0),
            ),
          ),
        );
      },
    );
  }
}
