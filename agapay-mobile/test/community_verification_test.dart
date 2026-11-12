// R4: unverified sensor incidents/observations are never presented as
// operational warnings. Synthetic fixtures only; no network or push provider.
import 'dart:convert';
import 'package:agapay_mobile/core/ui.dart';
import 'package:agapay_mobile/models/community_alert.dart';
import 'package:agapay_mobile/models/monitoring.dart';
import 'package:agapay_mobile/screens/alerts/alert_details_screen.dart';
import 'package:agapay_mobile/screens/alerts/alerts_screen.dart';
import 'package:agapay_mobile/screens/home/home_screen.dart';
import 'package:agapay_mobile/services/auth_api.dart';
import 'package:agapay_mobile/widgets/common/unverified_station_banner.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'support/accounts.dart';
import 'support/community_alerts.dart';

const evacuationInstruction = 'Prepare to evacuate';

AppController communityApp({required String? verification}) {
  final api = AuthApi(
    readerStorage: MemoryReaderStorage(),
    storage: MemoryTokens(),
    client: MockClient((r) async {
      final episode = communityEpisode(verification: verification);
      final body = r.url.path.endsWith('/501')
          ? {...communityDetail(), ...episode}
          : {'items': [episode], 'total': 1};
      return http.Response(jsonEncode(body), 200);
    }),
  );
  return AppController(
    locationSource: TestLocationSource(),
    preferenceStorage: MemoryProductPreferences(),
    authApi: api,
    sosStorage: MemorySosDrafts(),
  )..communityAlerts.setOwner(1);
}

Future<void> pumpScreen(
  WidgetTester tester,
  AppController app,
  Widget screen, {
  required ThemeData theme,
  double textScale = 1,
  Size size = const Size(390, 1600),
}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await tester.pumpWidget(
    AppScope(
      controller: app,
      child: MaterialApp(
        theme: theme,
        builder: (context, child) => MediaQuery(
          data: MediaQuery.of(
            context,
          ).copyWith(textScaler: TextScaler.linear(textScale)),
          child: child!,
        ),
        home: Scaffold(body: screen),
      ),
    ),
  );
  await tester.pump();
  await tester.pump();
}

Future<void> unmount(WidgetTester tester, AppController app) async {
  await tester.pumpWidget(const SizedBox.shrink());
  app.dispose();
  await tester.pump();
}

Map<String, Object?> monitoringFor({required bool reviewed}) => {
  'observation_tier': 'EVACUATE',
  'alert_tier': 'EVACUATE',
  'active_hazard_tier': 'EVACUATE',
  'current_depth_cm': 105.0,
  'latest_depth_cm': 105.0,
  if (reviewed) ...{
    'configuration': {
      'status': 'matched',
      'validation_status': 'field_reviewed',
    },
    'lifecycle': {'state': 'active'},
  } else ...{
    'configuration': {'status': 'matched', 'validation_status': 'prototype'},
    'lifecycle': {'state': 'active'},
  },
};

void main() {
  group('parser fails closed', () {
    test('operational is the only verified value', () {
      expect(
        CommunityAlert.fromJson(
          communityEpisode(verification: 'operational'),
        ).isOperational,
        isTrue,
      );
      for (final value in ['unverified', 'verified', 'OPERATIONAL', '', null]) {
        final a = CommunityAlert.fromJson(
          communityEpisode(verification: value),
        );
        expect(a.isOperational, isFalse, reason: 'value $value');
        expect(a.verification, CommunityAlertVerification.unverified);
      }
    });

    test('monitoring tier is operational only with every review field', () {
      MonitoringStation station(Map<String, Object?> changes) =>
          MonitoringStation.fromJson({
            'station_id': 'S',
            'station_name': 'S',
            'connection_status': 'online',
            'is_online': true,
            'is_stale': false,
            'source': 'device',
            'threshold_advisory_cm': 60,
            'threshold_warning_cm': 85,
            'threshold_evacuate_cm': 100,
            'history': <Object?>[],
            'depth_source_trusted': true,
            'configuration': {
              'status': 'matched',
              'validation_status': 'field_reviewed',
            },
            'lifecycle': {'state': 'active'},
            ...changes,
          });
      for (final change in <Map<String, Object?>>[
        {'depth_source_trusted': false},
        {
          'configuration': {'status': 'matched', 'validation_status': 'bench_reviewed'},
        },
        {
          'configuration': {'status': 'mismatch', 'validation_status': 'field_reviewed'},
        },
        {
          'lifecycle': {'state': 'maintenance'},
        },
        {'configuration': null, 'lifecycle': null},
      ]) {
        expect(
          station(change).operationallyVerified,
          isFalse,
          reason: '$change',
        );
      }
      expect(station({}).operationallyVerified, isTrue);
    });
  });

  for (final theme in [AppTheme.light, AppTheme.dark]) {
    final mode = theme.brightness.name;
    testWidgets('unverified list is labelled, not operational ($mode, 2x text, 320px)', (
      tester,
    ) async {
      final app = communityApp(verification: 'unverified');
      await pumpScreen(
        tester,
        app,
        const AlertsScreen(),
        theme: theme,
        textScale: 2,
        size: const Size(320, 4000),
      );
      expect(find.text(unverifiedStationTitle), findsOneWidget);
      expect(find.text('Recorded EVACUATE reading'), findsOneWidget);
      expect(find.text('EVACUATE'), findsNothing);
      expect(
        find.textContaining('Includes unverified station records'),
        findsOneWidget,
      );
      expect(
        find.textContaining('not an operational warning · View history'),
        findsOneWidget,
      );
      expect(
        find.bySemanticsLabel(RegExp('UNVERIFIED STATION')),
        findsOneWidget,
      );
      expect(tester.takeException(), isNull);
      await unmount(tester, app);
    });

    testWidgets('unverified detail never gives an evacuation instruction ($mode)', (
      tester,
    ) async {
      final app = communityApp(verification: 'unverified')
        ..showCommunityAlert(501);
      await pumpScreen(
        tester,
        app,
        const AlertDetailsScreen(),
        theme: theme,
        textScale: 1.5,
      );
      expect(find.text(unverifiedStationTitle), findsOneWidget);
      expect(find.textContaining(evacuationInstruction), findsNothing);
      expect(
        find.textContaining('not an evacuation instruction'),
        findsWidgets,
      );
      // Diagnostic history and shelter access remain available.
      expect(find.text('NORMAL → EVACUATE'), findsOneWidget);
      expect(find.text('VIEW EVACUATION MAP'), findsOneWidget);
      expect(tester.takeException(), isNull);
      await unmount(tester, app);
    });

    testWidgets('unverified station on home is a measurement, not a warning ($mode)', (
      tester,
    ) async {
      final app = fixtureController(
        monitoringChanges: monitoringFor(reviewed: false),
      );
      await app.login('resident@example.com', 'password123');
      await pumpScreen(tester, app, const HomeScreen(), theme: theme, textScale: 1.5);
      expect(find.text(unverifiedStationTitle), findsOneWidget);
      expect(find.text('Observed water depth · unverified station'), findsOneWidget);
      expect(find.textContaining(evacuationInstruction), findsNothing);
      expect(tester.takeException(), isNull);
      await pumpScreen(tester, app, const AlertDetailsScreen(), theme: theme);
      expect(find.text(unverifiedStationTitle), findsOneWidget);
      expect(find.textContaining(evacuationInstruction), findsNothing);
      expect(find.textContaining('Unverified station measurement'), findsWidgets);
      await unmount(tester, app);
    });
  }

  testWidgets('verified incident keeps the original operational presentation', (
    tester,
  ) async {
    final app = communityApp(verification: 'operational')
      ..showCommunityAlert(501);
    await pumpScreen(tester, app, const AlertDetailsScreen(), theme: AppTheme.dark);
    expect(find.byType(UnverifiedStationBanner), findsNothing);
    expect(find.text('EVACUATE'), findsOneWidget);
    expect(find.textContaining(evacuationInstruction), findsOneWidget);
    await unmount(tester, app);
  });

  testWidgets('reviewed station keeps operational home guidance', (tester) async {
    final app = fixtureController(
      monitoringChanges: monitoringFor(reviewed: true),
    );
    await app.login('resident@example.com', 'password123');
    await pumpScreen(tester, app, const HomeScreen(), theme: AppTheme.light);
    expect(find.byType(UnverifiedStationBanner), findsNothing);
    expect(find.textContaining(evacuationInstruction), findsOneWidget);
    await unmount(tester, app);
  });
}
