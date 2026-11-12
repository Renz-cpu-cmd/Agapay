import 'package:agapay_mobile/core/ui.dart';
import 'package:agapay_mobile/screens/alerts/alert_details_screen.dart';
import 'package:agapay_mobile/screens/home/home_screen.dart';
import 'package:agapay_mobile/widgets/common/hybrid_trend_panels.dart';
import 'package:agapay_mobile/widgets/common/water_level_gauge.dart';
import 'package:flutter_test/flutter_test.dart';
import 'support/accounts.dart';
import 'monitoring_contract_test.dart' show controllerFor, retainedStation;

void main() {
  for (final status in ['no_data', 'maintenance', 'inactive']) {
    test('$status is not presented as an unexpected heartbeat outage', () {
      final at = DateTime.now().toUtc();
      final controller = controllerFor(at, {
        ...retainedStation(at),
        'connection_status': status,
        'is_online': false,
        'heartbeat_fresh': false,
      });
      addTearDown(controller.dispose);
      expect(controller.primaryView!.heartbeat.status, status);
      expect(controller.primaryView!.heartbeat.fresh, isFalse);
    });
  }
  test(
    'compact chart labels use Philippine time across a UTC date boundary',
    () {
      final at = DateTime.utc(2026, 10, 23, 23, 30);
      expect(chartAxisTime(at), '24 Oct · 07:30:00');
      // Detailed evidence retains the original absolute timestamp.
      expect(chartTime(at), '2026-10-23T23:30:00.000Z');
    },
  );
  testWidgets('valid depth without a tier does not claim measurement absence', (
    tester,
  ) async {
    final app = fixtureController(
      monitoringChanges: {'observation_tier': null},
    );
    await app.login('resident@example.com', 'synthetic-password');
    await tester.pumpWidget(
      AppScope(
        controller: app,
        child: MaterialApp(
          theme: AppTheme.light,
          home: const Scaffold(body: HomeScreen()),
        ),
      ),
    );
    await tester.pump(const Duration(milliseconds: 100));
    expect(app.monitoring.primaryView!.depth.fresh, isTrue);
    expect(find.text('Observed water depth'), findsOneWidget);
    expect(
      find.textContaining('No valid measurement is available'),
      findsNothing,
    );
    expect(
      tester.widget<WaterLevelGauge>(find.byType(WaterLevelGauge)).level,
      95.8,
    );
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox.shrink());
    app.dispose();
  });
  testWidgets(
    'sensor detail keeps normal observed depth separate from a critical episode',
    (tester) async {
      final app = fixtureController(
        monitoringChanges: {
          'current_depth_cm': 0,
          'observation_tier': 'NORMAL',
          'alert_tier': 'EVACUATE',
          'active_hazard_tier': 'EVACUATE',
        },
      );
      await app.login('resident@example.com', 'synthetic-password');
      await tester.pumpWidget(
        AppScope(
          controller: app,
          child: MaterialApp(
            theme: AppTheme.light,
            home: const Scaffold(body: AlertDetailsScreen()),
          ),
        ),
      );
      await tester.pump(const Duration(milliseconds: 100));
      expect(find.text('Sensor episode: EVACUATE'), findsOneWidget);
      expect(find.text('0.0'), findsOneWidget);
      expect(
        tester.widget<Text>(find.text('0.0')).style!.color,
        isNot(
          tester
              .widget<Text>(find.text('Sensor episode: EVACUATE'))
              .style!
              .color,
        ),
      );
      expect(
        find.textContaining('Depth measurement time · PHT'),
        findsOneWidget,
      );
      expect(
        find.textContaining('sensor episode remains unresolved'),
        findsWidgets,
      );
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      app.dispose();
    },
  );
}
