// A7.1: an approximate registry position is never presented as an exact installation
// point, and device authentication is never worded as installation validation.
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
  'latitude': 15.98,
  'longitude': 120.56,
  'coordinate_status': 'verified',
  ...changes,
});

void main() {
  group('location label rules', () {
    final cases = <String, (Map<String, Object?>, String, bool)>{
      'bench: owner-confirmed ~1 km': (
        {'coordinate_precision_m': 1100, 'coordinate_basis': 'owner_confirmed'},
        'Approximate location (~1 km, owner-confirmed)',
        true,
      ),
      'estimated 300 m': (
        {'coordinate_precision_m': 300, 'coordinate_basis': 'estimated'},
        'Approximate location (~300 m, estimated)',
        true,
      ),
      'surveyed but coarse': (
        {'coordinate_precision_m': 200, 'coordinate_basis': 'surveyed'},
        'Approximate location (~200 m, surveyed)',
        true,
      ),
      'surveyed precise point': (
        {'coordinate_precision_m': 5, 'coordinate_basis': 'surveyed'},
        'Confirmed registry location (±5 m, surveyed)',
        false,
      ),
      'precision never recorded keeps existing wording': (
        <String, Object?>{},
        'Confirmed registry location',
        false,
      ),
      'unverified and approximate': (
        {
          'coordinate_status': 'unverified',
          'coordinate_precision_m': 1100,
          'coordinate_basis': 'owner_confirmed',
        },
        'Approximate unconfirmed location (~1 km, owner-confirmed)',
        true,
      ),
      'unverified, unrecorded': (
        {'coordinate_status': 'unverified'},
        'Unconfirmed registry location',
        false,
      ),
      'missing pair with stale precision: no pin': (
        {
          'latitude': null,
          'longitude': null,
          'coordinate_status': 'missing',
          'coordinate_precision_m': 1100,
          'coordinate_basis': 'owner_confirmed',
        },
        'Coordinates unavailable · no map pin',
        false,
      ),
      'invalid pair: no pin': (
        {
          'latitude': 95,
          'longitude': 120.5,
          'coordinate_precision_m': 1100,
          'coordinate_basis': 'owner_confirmed',
        },
        'Recorded location invalid · no map pin',
        false,
      ),
    };
    cases.forEach((name, value) {
      test(name, () {
        final s = station(value.$1);
        expect(s.locationLabel, value.$2);
        expect(s.locationApproximate, value.$3);
      });
    });

    test('authenticated device is not worded as validation', () {
      final s = station({'source_class': 'physical_device', 'source_trusted': true});
      expect(s.sourceLabel, 'Authenticated registered device');
      expect(s.sourceLabel.toLowerCase(), isNot(contains('verified')));
    });
  });

  for (final theme in [AppTheme.light, AppTheme.dark]) {
    testWidgets(
      '${theme.brightness.name}: approximate bench location is an area at 320px, 2x text',
      (tester) async {
        tester.view.physicalSize = const Size(320, 9000);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        final now = DateTime.now().toUtc();
        final app = fixtureController(observationClock: () => now);
        await app.login('resident@example.com', 'password123');
        app.monitoring.snapshot = MonitoringSnapshot.fromJson(
          snapshot(now, [
            {
              ...freshStation(now),
              'latitude': 15.98,
              'longitude': 120.56,
              'coordinate_status': 'verified',
              'coordinate_precision_m': 1100,
              'coordinate_basis': 'owner_confirmed',
              'source_class': 'physical_device',
              'source_trusted': true,
              'configuration': {'status': 'matched', 'validation_status': 'prototype'},
            },
            {
              ...freshStation(now, id: 'STATION_005'),
              'latitude': 15.9701,
              'longitude': 120.5702,
              'coordinate_status': 'verified',
              'coordinate_precision_m': 5,
              'coordinate_basis': 'surveyed',
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
        // Centred on the approximate bench station: zoomed out, with exactly one ring.
        expect(map.zoom, 13);
        expect(map.focusZoom, 13); // what the page applies to the selected marker
        expect(map.overlays.map((o) => o.id).toList(), ['precision-STATION_001']);
        final ring = map.overlays.single.points;
        expect(ring.first.latitude, closeTo(ring.last.latitude, 1e-9)); // closed
        expect(ring.first.longitude, closeTo(ring.last.longitude, 1e-9));
        // The pin stays at the registry pair; the ring never moves or adds pins (R1).
        final pin = map.markers.singleWhere((m) => m.id == 'STATION_001');
        expect((pin.position.latitude, pin.position.longitude), (15.98, 120.56));
        expect(map.markers.length, 2);
        expect(find.text('Approximate location (~1 km, owner-confirmed)'), findsOneWidget);
        expect(find.textContaining('the pin is not the exact installation point'), findsOneWidget);
        expect(find.text('Confirmed registry location'), findsNothing);
        expect(find.text('Authenticated registered device'), findsWidgets);
        expect(find.text('Registry-verified physical source'), findsNothing);
        // Prototype warnings are kept separately.
        expect(find.byType(UnverifiedStationBanner), findsNothing);
        // A genuinely surveyed station keeps its precise wording and close-up zoom.
        await tester.ensureVisible(find.widgetWithText(TextButton, 'STATION_005'));
        await tester.tap(find.widgetWithText(TextButton, 'STATION_005'));
        await tester.pumpAndSettle();
        final precise = tester.widget<AgapayGoogleMap>(find.byType(AgapayGoogleMap));
        expect(precise.zoom, 15);
        expect(precise.focusZoom, isNull); // unchanged close-up for a precise point
        expect(find.text('Confirmed registry location (±5 m, surveyed)'), findsOneWidget);
        expect(find.textContaining('the pin is not the exact installation point'), findsNothing);
        expect(tester.takeException(), isNull);
        await tester.pumpWidget(const SizedBox.shrink());
        app.dispose();
        await tester.pump();
      },
    );
  }
}
