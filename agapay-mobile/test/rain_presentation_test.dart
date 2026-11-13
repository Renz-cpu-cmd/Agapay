// A8: the rain-gauge figure states its coverage, calibration and origin from
// structured metadata. Missing metadata never becomes a claim of verified accuracy.
import 'package:agapay_mobile/core/ui.dart';
import 'package:agapay_mobile/models/monitoring.dart';
import 'package:agapay_mobile/screens/home/home_screen.dart';
import 'package:flutter_test/flutter_test.dart';
import 'support/accounts.dart';
import 'shared_freshness_test.dart' show freshStation, snapshot;

const hash = 'c5eed6b3f6b820c6a77342c4e30b64cbd9c46657eec086e115b5fff590d7557b';

Map<String, dynamic> product({
  bool complete = false,
  String quality = 'partial',
  String? calibration = hash,
  num? mmPerTip = 0.7,
  int? tips = 50,
}) => {
  'product': 'current_hour_received_tips',
  'rainfall_mm': (tips ?? 0) * (mmPerTip ?? 0),
  'tip_count': tips,
  'interval_start': '2026-11-13T05:00:00+00:00',
  'interval_end': '2026-11-13T05:43:00+00:00',
  'quality': quality,
  'coverage_complete': complete,
  'source': 'physical_rain_gauge',
  'coverage': complete ? 'complete' : 'missing or uncertain coverage; received tips only',
  'calibration_version': calibration,
  'mm_per_tip': mmPerTip,
};

Map<String, dynamic> config(String status, {String? configHash = hash, String match = 'matched'}) => {
  'status': match,
  'validation_status': status,
  'config_hash': configHash,
};

void main() {
  // Owner decision (2026-11-13): no qualifier labels on the rain card. The gauge's
  // manufacturer rating (0.7 mm/tip) is shown as the conversion. The internal `calibrated`
  // flag still follows the measured-water rule but no longer changes the wording.
  group('rain presentation rules', () {
    test('prototype: plain rainfall card with tips, coverage and conversion', () {
      final r = RainPresentation.from(product(), config('prototype'));
      expect((r.title, r.badge, r.amountSuffix, r.origin), ('RAINFALL', null, 'mm', null));
      expect(r.tips, '50 recorded tips');
      expect(r.coverage, 'Partial coverage');
      expect(r.calibration, 'Conversion: 0.7 mm/tip.');
      expect(r.caveat, 'Conversion: 0.7 mm/tip.');
      expect(r.calibrated, isFalse);
      for (final text in [r.title, r.amountSuffix, r.calibration, r.caveat]) {
        expect(text, isNot(matches(RegExp('calibrat|prototype|bench|unvalidated|equivalent|re-checked', caseSensitive: false))));
      }
    });

    test('calibrated flag still requires measured-water validation', () {
      expect(RainPresentation.from(product(), config('field_reviewed')).calibrated, isFalse);
      expect(RainPresentation.from(product(), config('field_reviewed'), physicalValidation: 'pending').calibrated, isFalse);
      final r = RainPresentation.from(product(complete: true, quality: 'complete'), config('field_reviewed'), physicalValidation: 'validated');
      expect(r.calibrated, isTrue);
      expect((r.title, r.badge, r.amountSuffix, r.calibration), ('RAINFALL', null, 'mm', 'Conversion: 0.7 mm/tip.'));
      expect(r.coverage, 'Complete coverage');
      expect(RainPresentation.from(product(), config('prototype'), physicalValidation: 'validated').calibrated, isFalse);
      expect(RainPresentation.from(product(calibration: 'other-hash'), config('field_reviewed'), physicalValidation: 'validated').calibrated, isFalse);
      expect(RainPresentation.from(product(), config('field_reviewed', match: 'mismatch'), physicalValidation: 'validated').calibrated, isFalse);
      expect(RainPresentation.from(product(calibration: null), config('field_reviewed')).calibrated, isFalse);
      expect(RainPresentation.from(product(), config('field_reviewed', configHash: null)).calibrated, isFalse);
    });

    test('complete flag with partial quality is still partial', () {
      expect(RainPresentation.from(product(complete: true), config('prototype')).coverage, 'Partial coverage');
    });

    test('missing configuration or product never invents a figure', () {
      final r = RainPresentation.from(product(), null);
      expect((r.calibrated, r.badge, r.origin), (false, null, null));
      final missing = RainPresentation.from(null, config('field_reviewed'));
      expect(missing.coverage, 'Coverage unknown');
      expect(missing.tips, isNull);
      expect(missing.calibration, 'Conversion unknown.');
      expect(missing.calibrated, isFalse);
    });
  });

  for (final theme in [AppTheme.light, AppTheme.dark]) {
    for (final fresh in [true, false]) {
      testWidgets('${theme.brightness.name} ${fresh ? 'fresh' : 'stale'}: rain card at 320px, 2x text', (tester) async {
        tester.view.physicalSize = const Size(320, 9000);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        final now = DateTime.now().toUtc();
        final app = fixtureController(observationClock: () => now);
        await app.login('resident@example.com', 'password123');
        app.monitoring.snapshot = MonitoringSnapshot.fromJson(snapshot(now, [
          {
            ...freshStation(now),
            'configuration': config('prototype'),
            'latest_rainfall_mm': 35.0,
            'rainfall_fresh': fresh,
            'rainfall_observed_at': now.toIso8601String(),
            'rainfall_age_seconds': fresh ? 2 : 7200,
            'rainfall_product': product(),
          },
        ]));
        app.monitoring.error = null;
        await tester.pumpWidget(AppScope(
          controller: app,
          child: MaterialApp(
            theme: theme,
            builder: (context, child) => MediaQuery(
              data: MediaQuery.of(context).copyWith(textScaler: const TextScaler.linear(2)),
              child: child!,
            ),
            home: const Scaffold(body: HomeScreen()),
          ),
        ));
        await tester.pump();
        expect(tester.takeException(), isNull);
        expect(find.text('RAINFALL'), findsOneWidget);
        expect(find.text('Prototype'), findsNothing);
        expect(find.text('35.0 mm'), findsOneWidget);
        expect(find.text('rainfall-equivalent'), findsNothing);
        expect(
          find.text(fresh ? '50 recorded tips · Partial coverage' : 'Last known / missing interval · Partial coverage'),
          findsOneWidget,
        );
        expect(
          find.text('Conversion: 0.7 mm/tip.'),
          findsOneWidget,
        );
        expect(find.text('Observed interval · journal'), findsNothing);
        await tester.pumpWidget(const SizedBox.shrink());
        app.dispose();
        await tester.pump();
      });
    }
  }
}
