import 'dart:async';
import 'dart:convert';
import 'package:agapay_mobile/controllers/monitoring_controller.dart';
import 'package:agapay_mobile/models/monitoring.dart';
import 'package:agapay_mobile/services/auth_api.dart';
import 'package:agapay_mobile/screens/home/home_screen.dart';
import 'package:agapay_mobile/screens/map/map_screen.dart';
import 'package:agapay_mobile/screens/alerts/alert_details_screen.dart';
import 'package:agapay_mobile/widgets/common/forecast_panel.dart';
import 'package:agapay_mobile/core/ui.dart';
import 'package:agapay_mobile/widgets/maps/agapay_google_map.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'support/accounts.dart';
import 'monitoring_contract_test.dart' show retainedStation;

Map<String, dynamic> freshStation(
  DateTime checked, {
  String id = 'STATION_001',
}) => {
  ...retainedStation(checked, depthAge: 0),
  'station_id': id,
  'sensor_quality': 'valid',
  'observation_tier': 'EVACUATE',
  'depth_fresh': true,
  'depth_status': 'fresh',
  'latitude': 15.97,
  'longitude': 120.57,
  // R4: these freshness tests describe a reviewed operational station.
  'configuration': {'status': 'matched', 'validation_status': 'field_reviewed'},
  'lifecycle': {'state': 'active'},
};
Map<String, dynamic> snapshot(DateTime at, List<Map<String, dynamic>> rows) => {
  'checked_at': at.toIso8601String(),
  'stale_after_seconds': 30,
  'stations': rows,
};
void main() {
  test(
    'one immutable view ages independent channels and cannot make invalid or untrusted depth live',
    () {
      var now = DateTime.now().toUtc();
      final at = now;
      final api = AuthApi(
        storage: MemoryTokens(),
        readerStorage: MemoryReaderStorage(),
        client: MockClient((_) async => http.Response('{}', 503)),
      );
      final c = MonitoringController(api, now: () => now);
      c.snapshot = MonitoringSnapshot.fromJson(
        snapshot(at, [freshStation(at)]),
      );
      final original = c.primaryView!;
      expect(original.depth.fresh, isTrue);
      expect(original.heartbeat.fresh, isTrue);
      expect(original.rain.fresh, isFalse);
      now = now.add(const Duration(seconds: 31));
      expect(c.primaryView!.depth.fresh, isFalse);
      expect(c.primaryView!.heartbeat.fresh, isFalse);
      expect(original.depth.fresh, isTrue);
      expect(() => c.snapshot!.stations.clear(), throwsUnsupportedError);
      expect(() => c.primary!.history.clear(), throwsUnsupportedError);
      c.snapshot = MonitoringSnapshot.fromJson(
        snapshot(now, [
          {...freshStation(now), 'sensor_quality': 'invalid'},
        ]),
      );
      expect(c.primaryView!.depth.status, 'invalid / retained');
      expect(c.primaryView!.heartbeat.fresh, isTrue);
      c.snapshot = MonitoringSnapshot.fromJson(
        snapshot(now, [
          {...freshStation(now), 'depth_source_trusted': false},
        ]),
      );
      expect(c.primaryView!.depth.fresh, isFalse);
      expect(c.primaryView!.depth.source, 'Unregistered depth source');
      c.dispose();
      api.dispose();
    },
  );
  test(
    'late old-account response and overlapping refresh cannot replace shared measurements',
    () async {
      final at = DateTime.now().toUtc(), old = Completer<http.Response>();
      var calls = 0;
      final api = AuthApi(
        storage: MemoryTokens(),
        readerStorage: MemoryReaderStorage(),
        client: MockClient((_) async {
          calls++;
          if (calls == 1) return old.future;
          return http.Response(
            jsonEncode(snapshot(at, [freshStation(at, id: 'STATION_002')])),
            200,
          );
        }),
      );
      final c = MonitoringController(api);
      c.setOwner(1);
      await Future<void>.delayed(Duration.zero);
      await c.refresh();
      expect(calls, 1);
      c.setOwner(2);
      await Future<void>.delayed(const Duration(milliseconds: 10));
      expect(c.primary?.id, 'STATION_002');
      old.complete(
        http.Response(jsonEncode(snapshot(at, [freshStation(at)])), 200),
      );
      await Future<void>.delayed(const Duration(milliseconds: 10));
      expect(c.primary?.id, 'STATION_002');
      c.setOwner(null);
      expect(c.primaryView, isNull);
      c.dispose();
      api.dispose();
    },
  );
  test(
    'release origins reject development and credential-bearing endpoints',
    () {
      for (final url in [
        'http://api.example.test',
        'http://10.0.2.2:8000',
        'https://localhost',
        'https://127.0.0.1',
        'https://192.168.1.1',
        'https://example.local',
        'https://user:secret@api.example.test',
        'https://api.example.test/api',
        'https://api.example.test?key=secret',
      ]) {
        expect(
          () => validateReleaseApiOrigin(url),
          throwsA(isA<AccountException>()),
        );
      }
      expect(
        validateReleaseApiOrigin('https://api.example.test/'),
        'https://api.example.test',
      );
    },
  );
  testWidgets(
    'home map detail and forecast expose the same source quality and freshness during disconnect and station change',
    (tester) async {
      final app = fixtureController();
      await app.login('resident@example.com', 'password123');
      final at = DateTime.now().toUtc().subtract(const Duration(hours: 1));
      app.monitoring.snapshot = MonitoringSnapshot.fromJson(
        snapshot(at, [freshStation(at), freshStation(at, id: 'STATION_002')]),
      );
      app.monitoring.error = 'Synthetic disconnected feed';
      final texts = <String>[];
      for (final screen in [
        const HomeScreen(),
        const MapScreen(),
        const AlertDetailsScreen(),
        const SingleChildScrollView(child: ForecastPanel()),
      ]) {
        await tester.pumpWidget(
          AppScope(
            controller: app,
            child: MaterialApp(
              theme: AppTheme.light,
              home: Scaffold(body: screen),
            ),
          ),
        );
        await tester.pump();
        if (screen is HomeScreen) {
          final details = find.text('Measurement source and station details');
          await tester.ensureVisible(details);
          await tester.tap(details);
          await tester.pumpAndSettle();
        }
        if (screen is MapScreen) {
          final details = find.text('Source and measurement details').first;
          await tester.ensureVisible(details);
          await tester.tap(details);
          await tester.pumpAndSettle();
        }
        if (screen is AlertDetailsScreen) {
          final details = find.text('Source and measurement details');
          await tester.ensureVisible(details);
          await tester.tap(details);
          await tester.pumpAndSettle();
        }
        final statuses = tester
            .widgetList<Text>(
              find.byKey(const ValueKey('shared-monitoring-status')),
            )
            .map((w) => w.data!)
            .toList();
        expect(statuses, isNotEmpty);
        texts.add(statuses.first);
        if (screen is MapScreen) {
          await tester.pumpAndSettle();
          final map = tester.widget<AgapayGoogleMap>(
            find.byType(AgapayGoogleMap),
          );
          expect(
            map.markers.every((m) => m.color == const Color(0xffa855f7)),
            isTrue,
          );
        }
      }
      expect(texts.toSet().length, 1);
      expect(texts.first, contains('Water depth: Last known'));
      expect(texts.first, contains('Latest sample validity: valid'));
      expect(texts.first, contains('Connectivity: unconfirmed'));
      app.selectStation('STATION_002');
      await tester.pump();
      expect(app.monitoring.primaryView!.station.id, 'STATION_002');
      expect(app.forecasts.stationId, 'STATION_002');
      expect(
        tester
            .widget<Text>(
              find.byKey(const ValueKey('shared-monitoring-status')).first,
            )
            .data,
        contains('STATION_002'),
      );
      await tester.pumpWidget(const SizedBox.shrink());
      app.dispose();
      await tester.pump();
    },
  );

  testWidgets(
    'map markers expire on the shared clock tick before any successful refresh',
    (tester) async {
      var clock = DateTime.now().toUtc();
      final app = fixtureController(observationClock: () => clock);
      await app.login('resident@example.com', 'password123');
      app.monitoring.snapshot = MonitoringSnapshot.fromJson(
        snapshot(clock, [freshStation(clock)]),
      );
      app.monitoring.error = null;
      await tester.pumpWidget(
        AppScope(
          controller: app,
          child: MaterialApp(
            theme: AppTheme.light,
            home: const Scaffold(body: MapScreen()),
          ),
        ),
      );
      await tester.pump();
      await tester.pumpAndSettle();
      expect(
        tester
            .widget<AgapayGoogleMap>(find.byType(AgapayGoogleMap))
            .markers
            .single
            .color,
        const Color(0xffef4444),
      );
      clock = clock.add(const Duration(seconds: 31));
      await tester.pump(const Duration(seconds: 1));
      expect(
        tester
            .widget<AgapayGoogleMap>(find.byType(AgapayGoogleMap))
            .markers
            .single
            .color,
        const Color(0xffa855f7),
      );
      expect(app.monitoring.primaryView!.depth.fresh, isFalse);
      expect(app.monitoring.error, isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      app.dispose();
      await tester.pump();
    },
  );
}
