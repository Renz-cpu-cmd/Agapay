import '../core/ui.dart';
import '../screens/home/home_screen.dart';
import '../screens/map/map_screen.dart';
import '../screens/alerts/alerts_screen.dart';
import '../screens/alerts/alert_details_screen.dart';
import '../screens/sos/sos_screen.dart';
import '../screens/profile/profile_screen.dart';

class MainNavigationShell extends StatelessWidget {
  const MainNavigationShell({super.key});
  static const _screens = [
    HomeScreen(key: PageStorageKey('home')),
    MapScreen(key: PageStorageKey('map')),
    SosScreen(key: PageStorageKey('sos')),
    AlertsScreen(key: PageStorageKey('alerts')),
    ProfileScreen(key: PageStorageKey('profile')),
  ];
  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context);
    return PopScope(
      canPop: !app.details,
      onPopInvokedWithResult: (didPop, result) {
        if (!didPop && app.details) {
          app.closeDetails();
        }
      },
      child: Scaffold(
        body: SafeArea(
          bottom: false,
          child: Stack(
            children: [
              Offstage(
                offstage: app.details,
                child: IndexedStack(
                  index: app.tab.index,
                  children: [
                    for (var i = 0; i < _screens.length; i++)
                      TickerMode(
                        enabled: !app.details && i == app.tab.index,
                        child: _screens[i],
                      ),
                  ],
                ),
              ),
              if (app.details) const AlertDetailsScreen(),
            ],
          ),
        ),
        bottomNavigationBar: AgapayBottomNav(),
      ),
    );
  }
}

class AgapayBottomNav extends StatelessWidget {
  const AgapayBottomNav({super.key});
  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context);
    const labels = ['Home', 'Map', 'SOS', 'Alerts', 'Profile'];
    const icons = ['home', 'map', 'sos', 'bell', 'user'];
    return Container(
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [AppColors.surfaceRaised, AppColors.background],
        ),
        border: Border(top: BorderSide(color: AppColors.border, width: 1.25)),
        boxShadow: [
          BoxShadow(
            color: Color(0x66000000),
            blurRadius: 18,
            offset: Offset(0, -5),
          ),
        ],
      ),
      child: SafeArea(
        top: false,
        child: SizedBox(
          height: 74,
          child: Row(
            children: [
              for (var i = 0; i < labels.length; i++)
                Expanded(
                  child: Semantics(
                    label: '${labels[i]} tab',
                    button: true,
                    selected: app.tab.index == i,
                    child: ExcludeSemantics(
                      child: InkWell(
                        onTap: () => app.navigate(AppTab.values[i]),
                        child: i == 2
                            ? Stack(
                                clipBehavior: Clip.none,
                                alignment: Alignment.topCenter,
                                children: [
                                  Positioned(
                                    top: -14,
                                    child: Column(
                                      children: [
                                        Container(
                                          width: 62,
                                          height: 62,
                                          decoration: BoxDecoration(
                                            color: AppColors.red,
                                            shape: BoxShape.circle,
                                            boxShadow:
                                                app.alert != AlertLevel.normal
                                                ? const [
                                                    BoxShadow(
                                                      color: Color(0x80dc2626),
                                                      blurRadius: 16,
                                                    ),
                                                  ]
                                                : null,
                                          ),
                                          child: const Center(
                                            child: SvgIcon(
                                              'sos',
                                              size: 27,
                                              color: Colors.white,
                                            ),
                                          ),
                                        ),
                                        const SizedBox(height: 5),
                                        tx(
                                          'SOS',
                                          size: 11,
                                          display: true,
                                          weight: 600,
                                          color: const Color(0xfff87171),
                                        ),
                                      ],
                                    ),
                                  ),
                                ],
                              )
                            : Stack(
                                alignment: Alignment.center,
                                children: [
                                  Column(
                                    mainAxisAlignment: MainAxisAlignment.center,
                                    spacing: 5,
                                    children: [
                                      SvgIcon(
                                        icons[i],
                                        size: 23,
                                        color: app.tab.index == i
                                            ? AppColors.link
                                            : AppColors.muted,
                                      ),
                                      tx(
                                        labels[i],
                                        size: 11,
                                        weight: app.tab.index == i ? 700 : 500,
                                        display: true,
                                        color: app.tab.index == i
                                            ? AppColors.link
                                            : AppColors.muted,
                                      ),
                                    ],
                                  ),
                                  if (app.tab.index == i)
                                    const Positioned(
                                      bottom: 4,
                                      child: Dot(AppColors.link, size: 4),
                                    ),
                                ],
                              ),
                      ),
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
