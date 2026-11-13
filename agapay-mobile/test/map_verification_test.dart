// R4: the Map screen never presents an unverified station's recorded tier as an
// operational warning. Widget tests with the in-test map fallback; this is not a
// Google Maps rendering or physical-device acceptance test.
import 'package:agapay_mobile/core/ui.dart';
import 'package:agapay_mobile/models/monitoring.dart';
import 'package:agapay_mobile/screens/map/map_screen.dart';
import 'package:agapay_mobile/widgets/common/unverified_station_banner.dart';
import 'package:agapay_mobile/widgets/maps/agapay_google_map.dart';
import 'package:flutter_test/flutter_test.dart';
import 'support/accounts.dart';
import 'shared_freshness_test.dart' show freshStation, snapshot;

const red = Color(0xffef4444), purple = Color(0xffa855f7);

final unverifiedVariants = <String, Map<String, dynamic>>{
  'prototype': {
    'configuration': {'status': 'matched', 'validation_status': 'prototype'},
  },
  'bench_reviewed': {
    'configuration': {
      'status': 'matched',
      'validation_status': 'bench_reviewed',
    },
  },
  'missing metadata': {'configuration': null, 'lifecycle': null},
  'unknown status': {
    'configuration': {'status': 'matched', 'validation_status': 'approved'},
  },
  'configuration mismatch': {
    'configuration': {
      'status': 'mismatch',
      'validation_status': 'field_reviewed',
    },
  },
  'withdrawn eligibility': {
    'lifecycle': {'state': 'maintenance'},
  },
};

Future<AppController> mountMap(
  WidgetTester tester,
  Map<String, dynamic> unverifiedChanges, {
  ThemeData? theme,
  double textScale = 1,
  Size size = const Size(390, 2400),
  DateTime Function()? clock,
}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  final now = DateTime.now().toUtc();
  final app = fixtureController(observationClock: clock ?? () => now);
  await app.login('resident@example.com', 'password123');
  final at = (clock ?? () => now)();
  app.monitoring.snapshot = MonitoringSnapshot.fromJson(
    snapshot(at, [
      freshStation(at), // reviewed, verified
      {
        ...freshStation(at, id: 'STATION_002'),
        'longitude': 120.58,
        ...unverifiedChanges,
      },
    ]),
  );
  app.monitoring.error = null;
  await tester.pumpWidget(
    AppScope(
      controller: app,
      child: MaterialApp(
        theme: theme ?? AppTheme.light,
        builder: (context, child) => MediaQuery(
          data: MediaQuery.of(
            context,
          ).copyWith(textScaler: TextScaler.linear(textScale)),
          child: child!,
        ),
        home: const Scaffold(body: MapScreen()),
      ),
    ),
  );
  await tester.pump();
  await tester.pumpAndSettle();
  return app;
}

AgapayGoogleMapMarker marker(WidgetTester tester, String id) => tester
    .widget<AgapayGoogleMap>(find.byType(AgapayGoogleMap))
    .markers
    .singleWhere((m) => m.id == id);

Future<void> unmount(WidgetTester tester, AppController app) async {
  await tester.pumpWidget(const SizedBox.shrink());
  app.dispose();
  await tester.pump();
}

void main() {
  // Owner decision (2026-11-13): verification notices are hidden; an unreviewed station's
  // pin and card use the same tier presentation as a reviewed one.
  for (final variant in unverifiedVariants.entries) {
    testWidgets('${variant.key}: recorded EVACUATE shows its tier colour without notices', (
      tester,
    ) async {
      expect(showStationVerificationNotices, isFalse);
      final app = await mountMap(tester, variant.value);
      final unreviewed = marker(tester, 'STATION_002');
      expect((unreviewed.color, unreviewed.glyph), (red, 'S'));
      expect(unreviewed.title, isNot(contains(unverifiedStationTitle)));
      expect(find.byKey(const ValueKey('map-unverified-STATION_002')), findsNothing);
      expect(find.textContaining('nverified'), findsNothing);
      final reviewed = marker(tester, 'STATION_001');
      expect((reviewed.color, reviewed.glyph), (red, 'S'));
      expect(find.text('EVACUATE'), findsNWidgets(2));
      expect(tester.takeException(), isNull);
      await unmount(tester, app);
    });
  }

  testWidgets('switching stations keeps each station\'s tier presentation', (
    tester,
  ) async {
    final app = await mountMap(tester, unverifiedVariants['prototype']!);
    for (final id in ['STATION_002', 'STATION_001', 'STATION_002', 'STATION_001']) {
      final button = find.widgetWithText(TextButton, id);
      await tester.ensureVisible(button);
      await tester.tap(button);
      await tester.pumpAndSettle();
      expect(app.monitoring.primary!.id, id);
      expect(
        tester.widget<AgapayGoogleMap>(find.byType(AgapayGoogleMap)).selectedMarkerId,
        id,
      );
      expect(marker(tester, 'STATION_002').color, red);
      expect(marker(tester, 'STATION_001').color, red);
      expect(find.textContaining('nverified'), findsNothing);
    }
    await unmount(tester, app);
  });

  testWidgets('stale readings never appear as a fresh tier', (tester) async {
    var clock = DateTime.now().toUtc();
    final app = await mountMap(
      tester,
      unverifiedVariants['prototype']!,
      clock: () => clock,
    );
    clock = clock.add(const Duration(seconds: 31));
    await tester.pump(const Duration(seconds: 1));
    await tester.pumpAndSettle();
    expect(marker(tester, 'STATION_001').color, purple);
    expect(marker(tester, 'STATION_002').color, purple);
    expect(find.text('UNKNOWN · reading not current'), findsNWidgets(2));
    expect(find.text('EVACUATE'), findsNothing);
    await unmount(tester, app);
  });

  for (final theme in [AppTheme.light, AppTheme.dark]) {
    testWidgets('${theme.brightness.name}: 320px at 2x text, legend and screen reader', (
      tester,
    ) async {
      final semantics = tester.ensureSemantics();
      final app = await mountMap(
        tester,
        unverifiedVariants['prototype']!,
        theme: theme,
        textScale: 2,
        size: const Size(320, 6000),
      );
      expect(tester.takeException(), isNull);
      expect(find.text('Unverified station · not a warning'), findsNothing);
      expect(find.text(unverifiedStationTitle), findsNothing);
      expect(find.bySemanticsLabel(RegExp('UNVERIFIED STATION')), findsNothing);
      final details = find.text('Source and measurement details');
      for (var i = 0; i < 2; i++) {
        await tester.ensureVisible(details.at(i));
        await tester.tap(details.at(i));
        await tester.pumpAndSettle();
      }
      final statuses = tester
          .widgetList<Text>(find.byKey(const ValueKey('shared-monitoring-status')))
          .map((w) => w.data!)
          .toList();
      expect(statuses.where((s) => s.contains('UNVERIFIED')), isEmpty);
      expect(
        statuses.where((s) => s.contains('Verification: AGAPAY field-reviewed')),
        hasLength(1),
      );
      expect(tester.takeException(), isNull);
      semantics.dispose();
      await unmount(tester, app);
    });
  }

  testWidgets('map controls and evacuation navigation still work', (tester) async {
    final app = await mountMap(tester, unverifiedVariants['prototype']!);
    final hide = find.text('Hide station map');
    await tester.ensureVisible(hide);
    await tester.tap(hide);
    await tester.pumpAndSettle();
    expect(find.byType(AgapayGoogleMap), findsNothing);
    await tester.ensureVisible(find.text('Show station map'));
    await tester.tap(find.text('Show station map'));
    await tester.pumpAndSettle();
    expect(find.byType(AgapayGoogleMap), findsOneWidget);
    await tester.ensureVisible(find.text('Evacuation Route'));
    await tester.tap(find.text('Evacuation Route'));
    await tester.pumpAndSettle();
    expect(app.evacuationMap, isTrue);
    expect(find.byType(UnverifiedStationBanner), findsNothing);
    await unmount(tester, app);
  });
}
