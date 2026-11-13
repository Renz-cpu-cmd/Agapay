import 'dart:async';
import 'package:agapay_mobile/core/ui.dart';
import 'package:agapay_mobile/screens/home/home_screen.dart';
import 'package:agapay_mobile/screens/alerts/alert_details_screen.dart';
import 'package:agapay_mobile/widgets/common/water_level_gauge.dart';
import 'package:flutter_test/flutter_test.dart';
import 'support/accounts.dart';

Future<void> mount(
  WidgetTester tester,
  AppController app, {
  bool details = false,
}) async {
  await tester.pumpWidget(
    AppScope(
      controller: app,
      child: MaterialApp(
        theme: AppTheme.light,
        home: Scaffold(
          body: details ? const AlertDetailsScreen() : const HomeScreen(),
        ),
      ),
    ),
  );
  await tester.pump(const Duration(milliseconds: 50));
}

void expectUnknownHome(WidgetTester tester, AppController app) {
  expect(find.text('UNKNOWN'), findsOneWidget);
  expect(find.text('95.8'), findsNothing);
  expect(find.textContaining('6.4 mm'), findsNothing);
  expect(find.textContaining('+3.2 cm'), findsNothing);
  expect(find.text('EXERCISE WORKSPACE'), findsNothing);
  expect(app.alert, isNull);
  expect(
    tester.widget<WaterLevelGauge>(find.byType(WaterLevelGauge)).level,
    isNull,
  );
  expect(tester.takeException(), isNull);
}

void main() {
  for (final scenario in [
    'new account',
    'empty station',
    'invalid station',
    'failed API',
    'login delay',
  ]) {
    testWidgets('$scenario never fabricates a hazard or measurements', (
      tester,
    ) async {
      final pending = Completer<void>();
      final app = fixtureController(
        emptyStations: scenario == 'new account',
        monitoringStatus: scenario == 'failed API' ? 503 : 200,
        monitoringReady: scenario == 'login delay' ? pending.future : null,
        monitoringChanges:
            ['empty station', 'invalid station'].contains(scenario)
            ? {
                'current_depth_cm': null,
                'latest_depth_cm': null,
                'latest_rainfall_mm': null,
                'last_valid_depth_at': null,
                'sensor_quality': scenario == 'invalid station'
                    ? 'invalid'
                    : null,
                'depth_fresh': false,
                'depth_status': 'missing',
                'alert_tier': null,
                'active_hazard_tier': null,
                'hazard_state': 'unknown',
                'history': <dynamic>[],
              }
            : {},
      );
      await app.login('resident@example.com', 'password123');
      await mount(tester, app);
      expectUnknownHome(tester, app);
      expect(find.text('San Vicente, Urdaneta'), findsNothing);
      if (scenario == 'login delay') {
        expect(app.monitoring.loading, isTrue);
        pending.complete();
      }
      if (scenario == 'failed API') expect(app.monitoring.error, isNotNull);
      if (scenario != 'login delay') {
        await mount(tester, app, details: true);
        expect(find.textContaining('Observation tier: UNKNOWN'), findsWidgets);
        expect(find.text('Sensor episode: None recorded'), findsOneWidget);
        expect(find.text('95.8'), findsNothing);
        expect(find.textContaining('6.4 mm'), findsNothing);
        expect(find.textContaining('Demo'), findsNothing);
        expect(tester.takeException(), isNull);
      }
      await tester.pumpWidget(const SizedBox.shrink());
      app.dispose();
      await tester.pump();
    });
  }

  testWidgets(
    'valid zero and an unresolved warning episode remain separate on home and details',
    (tester) async {
      final app = fixtureController(
        monitoringChanges: {
          'current_depth_cm': 0,
          'latest_depth_cm': 0,
          'latest_rainfall_mm': 0,
          'rainfall_fresh': true,
          'rainfall_age_seconds': 0,
          'rainfall_product': {
            'rainfall_mm': 0,
            'interval_start': '2026-10-22T00:00:00Z',
            'interval_end': '2026-10-22T00:00:10Z',
            'source': 'physical_rain_gauge',
            'coverage': 'synthetic received-tip interval',
            'calibration_version': 'test',
          },
          'alert_tier': 'WARNING',
          'active_hazard_tier': 'WARNING',
          'hazard_state': 'unresolved',
          'observation_tier': 'NORMAL',
        },
      );
      await app.login('resident@example.com', 'password123');
      await mount(tester, app);
      expect(find.text('0.0'), findsWidgets);
      expect(find.text('Observed · NORMAL'), findsOneWidget);
      expect(find.textContaining('Observed'), findsWidgets);
      expect(
        tester.widget<WaterLevelGauge>(find.byType(WaterLevelGauge)).level,
        0,
      );
      await mount(tester, app, details: true);
      expect(find.text('0.0 mm'), findsOneWidget);
      expect(find.textContaining('Observation tier: NORMAL'), findsWidgets);
      expect(find.text('Sensor episode: WARNING'), findsOneWidget);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      app.dispose();
    },
  );

  testWidgets(
    'exercise entry is explicit and scenario changes never mutate operational state',
    (tester) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final app = fixtureController(emptyStations: true);
      await app.login('resident@example.com', 'password123');
      await mount(tester, app);
      final original = app.monitoring.snapshot;
      expectUnknownHome(tester, app);
      final button = find.text('OPEN TEST WORKSPACE');
      await tester.ensureVisible(button);
      await tester.tap(button);
      await tester.pumpAndSettle();
      expect(find.text('EXERCISE WORKSPACE'), findsOneWidget);
      await tester.tap(find.text('WARNING'));
      await tester.pumpAndSettle();
      expect(find.text('EXERCISE WARNING'), findsOneWidget);
      expect(find.text('95.8 cm · EXAMPLE'), findsOneWidget);
      expect(app.alert, isNull);
      expect(identical(app.monitoring.snapshot, original), isTrue);
      final back = find.text('RETURN TO OPERATIONAL HOME');
      await tester.ensureVisible(back);
      await tester.tap(back);
      await tester.pumpAndSettle();
      expectUnknownHome(tester, app);
      await tester.pumpWidget(const SizedBox.shrink());
      app.dispose();
    },
  );
}
