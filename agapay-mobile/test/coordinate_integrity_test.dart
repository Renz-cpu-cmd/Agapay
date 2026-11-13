// R1: the resident map uses only validated registry positions. Missing or invalid
// coordinates produce no pin and no invented place; measurements are preserved.
import 'package:agapay_mobile/core/ui.dart';
import 'package:agapay_mobile/models/monitoring.dart';
import 'package:agapay_mobile/screens/map/map_screen.dart';
import 'package:agapay_mobile/widgets/common/unverified_station_banner.dart';
import 'package:agapay_mobile/widgets/maps/agapay_google_map.dart';
import 'package:flutter_test/flutter_test.dart';
import 'support/accounts.dart';
import 'shared_freshness_test.dart' show freshStation, snapshot;

MonitoringStation station(Map<String, Object?> changes) => MonitoringStation.fromJson({
  ...freshStation(DateTime.now().toUtc()),
  ...changes,
});

void main() {
  group('registry coordinate rules', () {
    final cases = <String, (Map<String, Object?>, String, bool)>{
      'verified pair': ({'latitude': 15.97, 'longitude': 120.57, 'coordinate_status': 'verified'}, 'verified', true),
      'older server without status': ({'latitude': 15.97, 'longitude': 120.57}, 'unverified', true),
      'zero latitude': ({'latitude': 0, 'longitude': 120.5, 'coordinate_status': 'verified'}, 'verified', true),
      'zero longitude': ({'latitude': 15.9, 'longitude': 0, 'coordinate_status': 'unverified'}, 'unverified', true),
      'both missing': ({'latitude': null, 'longitude': null}, 'missing', false),
      'latitude missing': ({'latitude': null, 'longitude': 120.5}, 'invalid', false),
      'longitude missing': ({'latitude': 15.9, 'longitude': null}, 'invalid', false),
      'latitude out of range': ({'latitude': 91, 'longitude': 120.5}, 'invalid', false),
      'longitude out of range': ({'latitude': 15.9, 'longitude': -181}, 'invalid', false),
      'server invalid': ({'latitude': null, 'longitude': null, 'coordinate_status': 'invalid'}, 'invalid', false),
    };
    for (final entry in cases.entries) {
      test(entry.key, () {
        final (changes, state, mapped) = entry.value;
        final s = station(changes);
        expect(s.locationState, state);
        expect(s.mapCoordinates != null, mapped);
      });
    }
    test('non-finite values are never mapped', () {
      final s = station({'latitude': 15.9, 'longitude': 120.5});
      expect(s.mapCoordinates, isNotNull);
      final nan = MonitoringStation.fromJson({
        ...freshStation(DateTime.now().toUtc()),
        'latitude': double.nan,
        'longitude': 120.5,
      });
      expect(nan.mapCoordinates, isNull);
      expect(nan.locationState, 'invalid');
    });
  });

  for (final theme in [AppTheme.light, AppTheme.dark]) {
    testWidgets('${theme.brightness.name}: map pins only registry positions at 320px, 2x text', (
      tester,
    ) async {
      tester.view.physicalSize = const Size(320, 9000);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final now = DateTime.now().toUtc();
      final app = fixtureController(observationClock: () => now);
      await app.login('resident@example.com', 'password123');
      const reviewed = {'status': 'matched', 'validation_status': 'field_reviewed'};
      app.monitoring.snapshot = MonitoringSnapshot.fromJson(
        snapshot(now, [
          {...freshStation(now), 'coordinate_status': 'verified'},
          {
            ...freshStation(now, id: 'STATION_002'),
            'latitude': null,
            'longitude': null,
            'coordinate_status': 'missing',
            'active_hazard_tier': 'EVACUATE',
          },
          {
            ...freshStation(now, id: 'STATION_003'),
            'latitude': null,
            'longitude': null,
            'coordinate_status': 'invalid',
          },
          {
            ...freshStation(now, id: 'STATION_004'),
            'latitude': 0,
            'longitude': 0,
            'coordinate_status': 'unverified',
            'configuration': {...reviewed, 'validation_status': 'prototype'},
          },
        ]),
      );
      app.monitoring.error = null;
      await tester.pumpWidget(
        AppScope(
          controller: app,
          child: MaterialApp(
            theme: theme,
            builder: (context, child) => MediaQuery(
              data: MediaQuery.of(context).copyWith(textScaler: const TextScaler.linear(2)),
              child: child!,
            ),
            home: const Scaffold(body: MapScreen()),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      final map = tester.widget<AgapayGoogleMap>(find.byType(AgapayGoogleMap));
      expect(map.markers.map((m) => m.id).toList(), ['STATION_001', 'STATION_004']);
      final zero = map.markers.singleWhere((m) => m.id == 'STATION_004');
      expect((zero.position.latitude, zero.position.longitude), (0.0, 0.0));
      expect(find.text('Confirmed registry location'), findsOneWidget);
      expect(find.text('Unconfirmed registry location'), findsOneWidget);
      expect(find.text('Coordinates unavailable · no map pin'), findsOneWidget);
      expect(find.text('Recorded location invalid · no map pin'), findsOneWidget);
      // Missing location preserves the measurement and the active episode.
      expect(find.textContaining('episode: EVACUATE'), findsWidgets);
      expect(find.text('Observed water depth'), findsNWidgets(4));
      // R4 verification is independent of location: the prototype station keeps its banner.
      expect(find.byKey(const ValueKey('map-unverified-STATION_004')), findsNothing);
      // Station switching never borrows another station's position.
      for (final id in ['STATION_002', 'STATION_004', 'STATION_003', 'STATION_001']) {
        await tester.ensureVisible(find.widgetWithText(TextButton, id));
        await tester.tap(find.widgetWithText(TextButton, id));
        await tester.pumpAndSettle();
        final markers = tester.widget<AgapayGoogleMap>(find.byType(AgapayGoogleMap)).markers;
        expect(markers.map((m) => m.id).toSet(), {'STATION_001', 'STATION_004'});
      }
      expect(find.byType(UnverifiedStationBanner), findsNothing);
      await tester.pumpWidget(const SizedBox.shrink());
      app.dispose();
      await tester.pump();
    });
  }
}
