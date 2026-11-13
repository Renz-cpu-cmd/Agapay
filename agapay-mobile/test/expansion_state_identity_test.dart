// Expansion panels and page scroll views must not share a PageStorage identity.
//
// Flutter stores both a scroll offset (double) and an expansion flag (bool) under an
// identifier built only from the PageStorageKeys above the widget. An unkeyed
// ExpansionTile directly inside a tab (PageStorageKey('home'), ('alerts'), ...) therefore
// shares the tab's scroll-offset slot. When the tile is recreated after the page was
// scrolled, Expansible.initState casts the double to bool? and throws:
// "type 'double' is not a subtype of type 'bool?' in type cast" (red error box seen on
// a physical Android phone after switching stations).
import 'dart:async';

import 'package:agapay_mobile/core/ui.dart';
import 'package:agapay_mobile/models/monitoring.dart';
import 'package:agapay_mobile/navigation/main_navigation_shell.dart';
import 'package:agapay_mobile/screens/home/home_screen.dart';
import 'package:agapay_mobile/screens/profile/privacy_screen.dart';
import 'package:agapay_mobile/widgets/common/unverified_station_banner.dart';
import 'package:flutter_test/flutter_test.dart';
import 'support/accounts.dart';
import 'shared_freshness_test.dart' show freshStation, snapshot;

late Completer<void> _refreshGate;
const _prototype = {'status': 'matched', 'validation_status': 'prototype'};

/// Valid depth samples so Home shows the water-depth trend chart and its panel.
List<Map<String, dynamic>> _history(DateTime now, double depth) => [
  for (var i = 5; i >= 0; i--)
    {
      'sequence_no': 6 - i,
      'water_depth_cm': depth,
      'sensor_quality': 'valid',
      'recorded_at': now.subtract(Duration(seconds: i * 5)).toIso8601String(),
    },
];

Future<AppController> _pumpShell(
  WidgetTester tester, {
  ThemeData? theme,
  double textScale = 1,
  Size size = const Size(390, 844),
}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  final now = DateTime.now().toUtc();
  // Hold the fixture's periodic refresh so the two synthetic stations stay in place.
  final app = fixtureController(
    observationClock: () => now,
    monitoringReady: (_refreshGate = Completer<void>()).future,
  );
  await app.login('resident@example.com', 'password123');
  app.monitoring.snapshot = MonitoringSnapshot.fromJson(
    snapshot(now, [
      // Unverified: Home shows the R4 banner above the trend panels.
      {...freshStation(now), 'configuration': _prototype, 'history': _history(now, 30)},
      // Reviewed: no banner, so the Home column changes shape on switch.
      {
        ...freshStation(now, id: 'STATION_002'),
        'observation_tier': 'WARNING',
        'history': _history(now, 90),
      },
    ]),
  );
  app.monitoring.error = null;
  app.monitoring.selectStation('STATION_001');
  await tester.pumpWidget(
    AppScope(
      controller: app,
      child: MaterialApp(
        theme: theme ?? AppTheme.dark,
        builder: (context, child) => MediaQuery(
          data: MediaQuery.of(context).copyWith(textScaler: TextScaler.linear(textScale)),
          child: child!,
        ),
        home: const MainNavigationShell(),
      ),
    ),
  );
  await tester.pump(const Duration(milliseconds: 300));
  return app;
}

Future<void> _settle(WidgetTester tester) async {
  for (var i = 0; i < 8; i++) {
    await tester.pump(const Duration(milliseconds: 100));
  }
}

/// Releases the held refresh, lets it complete, then disposes the controller.
Future<void> _finish(WidgetTester tester, AppController app) async {
  await tester.pumpWidget(const SizedBox.shrink());
  _refreshGate.complete();
  await tester.pump(const Duration(milliseconds: 50));
  app.dispose();
  await tester.pump();
}

/// Scrolls the visible tab page, which saves its offset (a double) to PageStorage.
Future<void> _scrollPage(WidgetTester tester, double dy) async {
  await tester.drag(find.byType(SingleChildScrollView).first, Offset(0, -dy));
  await _settle(tester);
}

/// What an ExpansionTile would read as its stored expansion state.
Object? _storedExpansion(WidgetTester tester, Finder tile) {
  final context = tester.element(tile);
  return PageStorage.maybeOf(context)?.readState(context);
}

Finder _tileTitled(String title) =>
    find.ancestor(of: find.text(title), matching: find.byType(ExpansionTile)).first;

void _expectNoFlutterError(WidgetTester tester) {
  expect(tester.takeException(), isNull);
  expect(find.byType(ErrorWidget), findsNothing);
}

void main() {
  testWidgets('Home: switching stations after scrolling never recreates a panel from the scroll offset', (
    tester,
  ) async {
    final app = await _pumpShell(tester);
    expect(find.text('View timestamped data'), findsWidgets);
    for (var round = 0; round < 3; round++) {
      await _scrollPage(tester, 900);
      app.monitoring.selectStation(round.isEven ? 'STATION_002' : 'STATION_001');
      await _settle(tester);
      _expectNoFlutterError(tester);
      // Station identity and verification labels are preserved across the switch.
      final id = round.isEven ? 'STATION_002' : 'STATION_001';
      final home = find.byType(HomeScreen, skipOffstage: false);
      expect(
        find.descendant(of: home, matching: find.textContaining('$id · Depth measured', skipOffstage: false)),
        findsOneWidget,
      );
      expect(
        find.descendant(of: home, matching: find.text(unverifiedStationTitle, skipOffstage: false)),
        findsNothing, // verification notices are not shown (owner decision)
      );
    }
    await _finish(tester, app);
  });

  testWidgets('Home: the timestamped-data panel keeps its own state, separate from page scroll', (
    tester,
  ) async {
    final app = await _pumpShell(tester);
    final tile = find.byKey(const PageStorageKey<String>('trend-data-water-depth'));
    final title = find.descendant(of: tile, matching: find.text('View timestamped data'));
    Future<void> toggle() async {
      // Centre the title so the floating SOS button cannot intercept the tap.
      await tester.ensureVisible(title);
      await Scrollable.ensureVisible(tester.element(title), alignment: .5);
      await _settle(tester);
      await tester.tap(title);
      await _settle(tester);
    }

    await toggle();
    expect(_storedExpansion(tester, tile), isTrue);
    expect(find.descendant(of: tile, matching: find.byType(ListTile)), findsWidgets);
    await _scrollPage(tester, 300);
    // Scrolling must not overwrite the panel's state, nor the panel the scroll offset.
    expect(_storedExpansion(tester, tile), isTrue);
    final offset = tester.state<ScrollableState>(find.byType(Scrollable).first).position.pixels;
    expect(offset, greaterThan(0));
    // Leave Home and come back: both states survive independently.
    app.navigate(AppTab.alerts);
    await _settle(tester);
    app.navigate(AppTab.home);
    await _settle(tester);
    expect(tester.state<ScrollableState>(find.byType(Scrollable).first).position.pixels, offset);
    expect(_storedExpansion(tester, tile), isTrue);
    // Station switch keeps the panel's own state and never reads the scroll offset.
    app.monitoring.selectStation('STATION_002');
    await _settle(tester);
    expect(_storedExpansion(tester, tile), isTrue);
    await toggle();
    expect(_storedExpansion(tester, tile), isFalse);
    _expectNoFlutterError(tester);
    await _finish(tester, app);
  });

  testWidgets('Alerts: the area-advisories panel does not share the page scroll slot', (tester) async {
    final app = await _pumpShell(tester);
    app.navigate(AppTab.alerts);
    await _settle(tester);
    final tile = _tileTitled('Advisories for your area');
    await _scrollPage(tester, 200);
    final stored = _storedExpansion(tester, tile);
    expect(stored, isNot(isA<double>()), reason: 'tile would read the scroll offset as its state');
    await tester.ensureVisible(tile);
    await _settle(tester);
    await tester.tap(find.text('Advisories for your area'));
    await _settle(tester);
    expect(_storedExpansion(tester, tile), isTrue);
    // Home, Alerts and the panel each keep independent state across tab switches.
    app.navigate(AppTab.home);
    await _settle(tester);
    app.navigate(AppTab.alerts);
    await _settle(tester);
    expect(_storedExpansion(tester, _tileTitled('Advisories for your area')), isTrue);
    _expectNoFlutterError(tester);
    await _finish(tester, app);
  });

  testWidgets('Profile: the subscription target list does not inherit the outer panel state', (
    tester,
  ) async {
    final app = await _pumpShell(tester, size: const Size(390, 2400));
    app.navigate(AppTab.profile);
    await _settle(tester);
    final outer = _tileTitled('Alert subscriptions');
    await tester.ensureVisible(outer);
    await _settle(tester);
    await tester.tap(find.text('Alert subscriptions'));
    await _settle(tester);
    expect(_storedExpansion(tester, outer), isTrue);
    final inner = _tileTitled('Choose stations and areas');
    // Opening the outer panel must not open (or be stored as) the inner one.
    expect(_storedExpansion(tester, inner), isNot(isTrue));
    expect(
      tester.widget<ExpansionTile>(inner).controller?.isExpanded ?? false,
      isFalse,
    );
    expect(
      tester.state(find.descendant(of: inner, matching: find.byType(Expansible))),
      isNotNull,
    );
    expect(
      find.descendant(of: inner, matching: find.byType(CheckboxListTile)).hitTestable(),
      findsNothing,
      reason: 'inner list stays collapsed until the resident opens it',
    );
    _expectNoFlutterError(tester);
    await _finish(tester, app);
  });

  testWidgets('Privacy (own route, no tab key) keeps a working, isolated panel', (tester) async {
    final app = await _pumpShell(tester);
    await tester.pumpWidget(
      AppScope(
        controller: app,
        child: MaterialApp(theme: AppTheme.light, home: const PrivacyScreen()),
      ),
    );
    await _settle(tester);
    final tile = _tileTitled('Data, recipients and retention');
    await _scrollPage(tester, 200);
    expect(_storedExpansion(tester, tile), isNot(isA<double>()));
    _expectNoFlutterError(tester);
    await _finish(tester, app);
  });

  for (final theme in [AppTheme.light, AppTheme.dark]) {
    testWidgets('${theme.brightness.name}: 320px, 2x text, repeated switches stay error-free', (
      tester,
    ) async {
      final app = await _pumpShell(tester, theme: theme, textScale: 2, size: const Size(320, 900));
      for (var round = 0; round < 4; round++) {
        await _scrollPage(tester, 1500);
        app.monitoring.selectStation(round.isEven ? 'STATION_002' : 'STATION_001');
        await _settle(tester);
        app.navigate(round.isEven ? AppTab.alerts : AppTab.profile);
        await _settle(tester);
        await _scrollPage(tester, 400);
        app.navigate(AppTab.home);
        await _settle(tester);
        _expectNoFlutterError(tester);
      }
      await _finish(tester, app);
    });
  }
}
