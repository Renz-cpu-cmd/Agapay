import '../core/ui.dart';
import '../widgets/common/offline_reader_banner.dart';
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
          child: Column(
            children: [
              const OfflineReaderBanner(),
              if (app.monitoring.snapshot?.serviceHealth?['status'] ==
                  'degraded')
                Padding(
                  padding: const EdgeInsets.all(8),
                  child: Text(
                    app.monitoring.snapshot!.serviceHealth!['message']
                            as String? ??
                        'Some live services are degraded. Check timestamps.',
                    style: const TextStyle(fontSize: 11),
                  ),
                ),
              Expanded(
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
    if (MediaQuery.textScalerOf(context).scale(14) > 24) {
      return Material(
        color: context.colors.surface,
        child: SafeArea(
          top: false,
          child: LayoutBuilder(
            builder: (context, constraints) {
              final style = DefaultTextStyle.of(
                context,
              ).style.copyWith(fontSize: 14, color: context.colors.text);
              var labelHeight = 0.0;
              for (final label in labels) {
                final painter = TextPainter(
                  text: TextSpan(text: label, style: style),
                  textDirection: Directionality.of(context),
                  textScaler: MediaQuery.textScalerOf(context),
                )..layout(maxWidth: constraints.maxWidth / 3);
                if (painter.height > labelHeight) labelHeight = painter.height;
                painter.dispose();
              }
              return Wrap(
                children: [
                  for (var i = 0; i < labels.length; i++)
                    SizedBox(
                      width: constraints.maxWidth / 3,
                      height: 48 + labelHeight,
                      child: Semantics(
                        label: '${labels[i]} tab',
                        selected: app.tab.index == i,
                        button: true,
                        child: ExcludeSemantics(
                          child: InkWell(
                            onTap: () => app.navigate(AppTab.values[i]),
                            child: Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                SvgIcon(
                                  icons[i],
                                  size: 24,
                                  color: app.tab.index == i
                                      ? context.colors.link
                                      : context.colors.muted,
                                ),
                                const SizedBox(height: 8),
                                Text(
                                  labels[i],
                                  textAlign: TextAlign.center,
                                  style: style.copyWith(
                                    color: app.tab.index == i
                                        ? context.colors.link
                                        : context.colors.muted,
                                    fontWeight: app.tab.index == i
                                        ? FontWeight.w700
                                        : FontWeight.w400,
                                  ),
                                ),
                                if (app.tab.index == i)
                                  Dot(context.colors.link, size: 4),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ),
                ],
              );
            },
          ),
        ),
      );
    }
    return Container(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [context.colors.surfaceRaised, context.colors.background],
        ),
        border: Border(
          top: BorderSide(color: context.colors.border, width: 1.25),
        ),
        boxShadow: [
          BoxShadow(
            color: context.colors.isDark
                ? const Color(0x66000000)
                : const Color(0x120f2748),
            blurRadius: 18,
            offset: Offset(0, -5),
          ),
        ],
      ),
      child: SafeArea(
        top: false,
        child: SizedBox(
          height:
              74 +
              32 * (MediaQuery.textScalerOf(context).scale(1) - 1).clamp(0, 2),
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
                                            color: context.colors.red,
                                            shape: BoxShape.circle,
                                            boxShadow:
                                                app.alert != null &&
                                                    app.alert !=
                                                        AlertLevel.unknown &&
                                                    app.alert !=
                                                        AlertLevel.normal
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
                                            ? context.colors.link
                                            : context.colors.muted,
                                      ),
                                      tx(
                                        labels[i],
                                        size: 11,
                                        weight: app.tab.index == i ? 700 : 500,
                                        display: true,
                                        color: app.tab.index == i
                                            ? context.colors.link
                                            : context.colors.muted,
                                      ),
                                    ],
                                  ),
                                  if (app.tab.index == i)
                                    Positioned(
                                      bottom: 4,
                                      child: Dot(context.colors.link, size: 4),
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
