import 'package:agapay_mobile/core/ui.dart';
import 'package:agapay_mobile/models/monitoring.dart';
import 'package:agapay_mobile/widgets/common/water_level_gauge.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:flutter_test/flutter_test.dart';
import 'monitoring_contract_test.dart' show retainedStation, controllerFor;
import 'support/accounts.dart' show fixtureController;
import 'package:agapay_mobile/widgets/common/hybrid_trend_panels.dart';

void main() {
  testWidgets(
    'rain interval and missing coverage stay visible without completed chart history',
    (tester) async {
      final app = fixtureController();
      await app.login('resident@example.com', 'test-password');
      await tester.pump();
      await app.hybrid.refresh();
      final rain = app.hybrid.data!.rain!;
      rain['completed_hours'] = <dynamic>[];
      rain['current_hour_product'] = {
        'interval_start': '2026-10-22T00:00:00Z',
        'interval_end': '2026-10-22T00:00:10Z',
        'coverage': 'missing receive coverage',
      };
      rain['calibration_version'] = 'synthetic-calibration';
      await tester.pumpWidget(
        AppScope(
          controller: app,
          child: MaterialApp(
            theme: AppTheme.light,
            home: const Scaffold(
              body: SingleChildScrollView(child: RainfallActivityPanel()),
            ),
          ),
        ),
      );
      await tester.pump();
      expect(find.textContaining('missing receive coverage'), findsOneWidget);
      expect(find.textContaining('physical_rain_gauge'), findsOneWidget);
      expect(find.textContaining('synthetic-calibration'), findsOneWidget);
      expect(
        find.text('No completed rainfall history available.'),
        findsOneWidget,
      );
      await tester.pumpWidget(const SizedBox.shrink());
      app.dispose();
    },
  );
  test(
    'legacy rainfall is unavailable; independent zero keeps interval, source and coverage',
    () {
      final checked = DateTime.now().toUtc();
      final raw = retainedStation(checked);
      expect(MonitoringStation.fromJson(raw).latestRainfallMm, isNull);
      raw['rainfall_product'] = {
        'rainfall_mm': 0,
        'interval_start': '2026-10-22T00:00:00Z',
        'interval_end': '2026-10-22T00:00:10Z',
        'source': 'physical_rain_gauge',
        'coverage': 'missing coverage; received tips only',
        'calibration_version': 'synthetic-review',
      };
      raw['rainfall_fresh'] = true;
      raw['rainfall_age_seconds'] = 0;
      raw['configuration'] = {
        'status': 'mismatch',
        'applied_config_hash': 'a',
        'config_hash': 'b',
      };
      final controller = controllerFor(checked, raw);
      addTearDown(controller.dispose);
      final station = controller.primary!;
      expect(station.latestRainfallMm, 0);
      expect(station.rainfallNote, contains('missing coverage'));
      expect(station.rainfallNote, contains('physical_rain_gauge'));
      expect(station.configuration?['status'], 'mismatch');
      expect(controller.isRainFresh(station), isTrue);
      controller.error = 'API unavailable';
      expect(controller.isRainFresh(station), isFalse);
    },
  );
  testWidgets(
    'gauge uses station thresholds and geometry instead of embedded defaults',
    (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.light,
          home: const Scaffold(
            body: WaterLevelGauge(
              45,
              advisory: 20,
              warning: 30,
              critical: 40,
              maximum: 150,
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('EVAC 40'), findsOneWidget);
      expect(find.text('WARN 30'), findsOneWidget);
      expect(find.text('ADV 20'), findsOneWidget);
      expect(find.text('EVAC 100'), findsNothing);
      final svg = tester.widget<SvgPicture>(find.byType(SvgPicture));
      final source = (svg.bytesLoader as SvgStringLoader).provideSvg(null);
      expect(source, contains('stop-color="#dc2626"'));
      expect(source, contains('height="54.0"'));
    },
  );
}
