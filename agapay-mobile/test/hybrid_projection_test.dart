import 'dart:async';
import 'dart:convert';
import 'package:agapay_mobile/controllers/hybrid_projection_controller.dart';
import 'package:agapay_mobile/controllers/app_controller.dart';
import 'package:agapay_mobile/core/theme/app_theme.dart';
import 'package:agapay_mobile/services/auth_api.dart';
import 'package:agapay_mobile/widgets/common/hybrid_trend_panels.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'support/accounts.dart';
import 'support/hybrid_projection.dart';

void main() {
  setUpAll(() async {
    TestWidgetsFlutterBinding.ensureInitialized();
    for (final name in ['Inter', 'Outfit', 'JetBrainsMono']) {
      final loader = FontLoader(name)
        ..addFont(rootBundle.load('assets/fonts/$name.ttf'));
      await loader.load();
    }
    final icons = FontLoader('MaterialIcons')
      ..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf'));
    await icons.load();
  });
  test(
    'strict hybrid contract rejects missing horizons, non-finite and unavailable numeric values',
    () {
      final raw = hybridFixture();
      expect(HybridProjection(raw).depths.length, 4);
      expect(
        () => HybridProjection({...raw, 'points': []}),
        throwsFormatException,
      );
      expect(
        () => HybridProjection({...raw, 'advisory_only': false}),
        throwsFormatException,
      );
      expect(
        () => HybridProjection({...raw, 'status': 'unavailable'}),
        throwsFormatException,
      );
      (raw['points'] as List).first['depth_cm'] = double.nan;
      expect(() => HybridProjection(raw), throwsFormatException);
    },
  );

  test(
    'summary preserves unknown rain, clears at rollover and expiry, and uses only read-only requests',
    () async {
      var at = DateTime.utc(2026, 10, 20, 12, 59, 59);
      final raw = rainActivityFixture(at: at);
      final methods = <String>[];
      final api = AuthApi(
        readerStorage: MemoryReaderStorage(),
        storage: MemoryTokens(),
        client: MockClient((r) async {
          methods.add(r.method);
          return http.Response(jsonEncode(raw), 200);
        }),
      );
      final feed = HybridProjectionController(api, now: () => at);
      feed.setOwner(1);
      await Future<void>.delayed(Duration.zero);
      expect(feed.available, isFalse);
      expect(feed.currentRainMm, .7);
      expect(feed.rainfallHours, [null, 0]);
      expect(methods.every((m) => m == 'GET'), isTrue);
      at = at.add(const Duration(seconds: 2));
      expect(feed.currentRainMm, isNull);
      at = at.add(const Duration(seconds: 31));
      expect(feed.expired, isFalse);
      expect(feed.available, isFalse);
      expect(feed.currentRainMm, isNull);
      feed.dispose();
      api.dispose();
    },
  );

  test(
    'late station and previous-account responses never replace the new selection',
    () async {
      final delayed = Completer<http.Response>();
      final api = AuthApi(
        readerStorage: MemoryReaderStorage(),
        storage: MemoryTokens(),
        client: MockClient((r) async {
          if (r.url.path.contains('STATION_001')) return delayed.future;
          return http.Response(
            jsonEncode(rainActivityFixture(station: 'STATION_002')),
            200,
          );
        }),
      );
      final feed = HybridProjectionController(api);
      feed.setOwner(1);
      feed.selectStation('STATION_002');
      await Future<void>.delayed(Duration.zero);
      expect(feed.data?.stationId, 'STATION_002');
      delayed.complete(http.Response(jsonEncode(rainActivityFixture()), 200));
      await Future<void>.delayed(Duration.zero);
      expect(feed.data?.stationId, 'STATION_002');
      feed.setOwner(null);
      expect(feed.data, isNull);
      feed.dispose();
      api.dispose();
    },
  );

  test(
    'simulated and wrong-station gauge snapshots cannot claim physical rainfall',
    () async {
      final raw = rainActivityFixture();
      final api = AuthApi(
        readerStorage: MemoryReaderStorage(),
        storage: MemoryTokens(),
        client: MockClient((r) async => http.Response(jsonEncode(raw), 200)),
      );
      final feed = HybridProjectionController(api);
      feed.setOwner(1);
      await Future<void>.delayed(Duration.zero);
      (raw['rain_activity'] as Map)['data_source'] = 'simulated_rain_gauge';
      await feed.refresh();
      expect(feed.gaugeFresh, isFalse);
      expect(feed.currentRainMm, isNull);
      (raw['rain_activity'] as Map)['data_source'] = 'physical_rain_gauge';
      (raw['rain_activity'] as Map)['station_id'] = 'OTHER';
      await feed.refresh();
      expect(feed.gaugeFresh, isFalse);
      feed.dispose();
      api.dispose();
    },
  );

  testWidgets(
    'resident trends fit narrow light and dark layouts, with staff controls hidden',
    (tester) async {
      tester.view.physicalSize = const Size(320, 900);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final app = fixtureController();
      await app.login('resident@example.com', 'test-password');
      await app.hybrid.refresh();
      for (final theme in [AppTheme.light, AppTheme.dark]) {
        await tester.pumpWidget(
          AppScope(
            controller: app,
            child: MaterialApp(
              theme: theme,
              home: const Scaffold(
                body: SingleChildScrollView(
                  child: Column(
                    children: [
                      WaterDepthTrendPanel(),
                      HybridForecastTrendPanel(),
                      RainfallActivityPanel(),
                    ],
                  ),
                ),
              ),
            ),
          ),
        );
        await tester.pump();
        expect(find.text('WATER DEPTH TREND'), findsOneWidget);
        expect(find.text('WATER-DEPTH FORECAST'), findsOneWidget);
        expect(find.text('RAINFALL ACTIVITY'), findsOneWidget);
        expect(find.text('ML Configuration & Evaluation →'), findsNothing);
        expect(tester.takeException(), isNull);
      }
      await tester.pumpWidget(const SizedBox.shrink());
      app.dispose();
    },
  );
}
