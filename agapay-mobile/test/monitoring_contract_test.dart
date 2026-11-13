import 'package:agapay_mobile/controllers/monitoring_controller.dart';
import 'package:agapay_mobile/core/ui.dart';
import 'package:agapay_mobile/models/monitoring.dart';
import 'package:agapay_mobile/screens/home/home_screen.dart';
import 'package:agapay_mobile/services/auth_api.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'support/accounts.dart';

Map<String, dynamic> retainedStation(
  DateTime checked, {
  int depthAge = 3600,
}) => {
  'station_id': 'STATION_001', 'station_name': 'Synthetic trusted station',
  'barangay': 'San Vicente', 'municipality': 'Urdaneta City',
  'connection_status': 'online', 'is_online': true, 'is_stale': true,
  'age_seconds': depthAge, 'heartbeat_age_seconds': 0, 'heartbeat_fresh': true,
  'depth_age_seconds': depthAge, 'depth_fresh': false, 'depth_status': 'stale',
  'heartbeat_at': checked.toIso8601String(),
  'latest_sample_at': checked.toIso8601String(),
  'last_valid_depth_at': checked
      .subtract(Duration(seconds: depthAge))
      .toIso8601String(),
  // The old ambiguous date must not override the retained depth's actual date.
  'observed_at': checked.toIso8601String(),
  'alert_tier': 'EVACUATE',
  'trend': 'stable',
  'current_depth_cm': 105, 'latest_depth_cm': null, 'latest_rainfall_mm': .7,
  'sensor_quality': 'invalid', 'firmware_version': '1.0.0-simulator',
  'source': 'device', 'source_class': 'physical_device', 'source_trusted': true,
  'depth_source_trusted': true, 'stream': 'operational',
  'hazard_state': 'unresolved', 'active_hazard_tier': 'EVACUATE',
  'threshold_advisory_cm': 60,
  'threshold_warning_cm': 85,
  'threshold_evacuate_cm': 100,
  'history': <dynamic>[],
};

MonitoringController controllerFor(
  DateTime checked,
  Map<String, dynamic> station,
) {
  final controller = MonitoringController(
    AuthApi(
      readerStorage: MemoryReaderStorage(),
      storage: MemoryTokens(),
      client: MockClient((_) async => http.Response('{}', 500)),
    ),
  );
  controller.snapshot = MonitoringSnapshot.fromJson({
    'checked_at': checked.toIso8601String(),
    'stale_after_seconds': 30,
    'stations': [station],
  });
  return controller;
}

void main() {
  test(
    'fresh invalid heartbeats stay connected without refreshing the retained depth',
    () {
      final checked = DateTime.now().toUtc();
      final controller = controllerFor(checked, retainedStation(checked));
      addTearDown(controller.dispose);
      final station = controller.primary!;
      expect(controller.isOnline(station), isTrue);
      expect(controller.isFresh(station), isFalse);
      expect(controller.depthAge(station), inInclusiveRange(3600, 3602));
      expect(controller.measurementAgeLabel(station), '1 hr ago');
      expect(
        station.observedAt,
        checked.subtract(const Duration(hours: 1)).toLocal(),
      );
      expect(station.hazardState, 'unresolved');
      expect(station.history, isEmpty); // Independent of the chart window.
    },
  );

  test(
    'cached values keep aging from server check time even when no new response arrives',
    () {
      final checked = DateTime.now().toUtc().subtract(
        const Duration(seconds: 60),
      );
      final controller = controllerFor(checked, retainedStation(checked));
      addTearDown(controller.dispose);
      expect(controller.isOnline(controller.primary!), isFalse);
      expect(
        controller.depthAge(controller.primary!),
        inInclusiveRange(3660, 3662),
      );
    },
  );

  test('firmware text and a device alias cannot grant registry provenance', () {
    final now = DateTime.now().toUtc();
    for (final firmware in ['1.0.0', '1.0.0-simulator']) {
      final row = {
        ...retainedStation(now),
        'firmware_version': firmware,
        'source_class': 'unverified',
        'source_trusted': false,
        'depth_source_trusted': false,
      };
      final station = MonitoringStation.fromJson(row);
      expect(station.sourceLabel, 'Unregistered source');
      expect(station.sourceTrusted, isFalse);
    }
  });

  testWidgets(
    'home shows online heartbeat, one-hour retained depth and unresolved hazard together',
    (tester) async {
      final checked = DateTime.now().toUtc();
      final app = fixtureController();
      app.monitoring.snapshot = MonitoringSnapshot.fromJson({
        'checked_at': checked.toIso8601String(),
        'stale_after_seconds': 30,
        'stations': [retainedStation(checked)],
      });
      await tester.pumpWidget(
        AppScope(
          controller: app,
          child: MaterialApp(
            theme: AppTheme.light,
            home: const Scaffold(body: HomeScreen()),
          ),
        ),
      );
      await tester.pump();
      expect(find.textContaining('Depth measured 1 hr ago'), findsWidgets);
      expect(find.textContaining('Device heartbeat: online'), findsOneWidget);
      expect(
        find.textContaining('Sensor episode unresolved · EVACUATE'),
        findsOneWidget,
      );
      expect(find.text('Observed'), findsNothing);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      app.dispose();
    },
  );
}
