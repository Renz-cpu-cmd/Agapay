import 'dart:async';
import 'dart:convert';
import 'package:agapay_mobile/controllers/app_controller.dart';
import 'package:agapay_mobile/controllers/forecast_controller.dart';
import 'package:agapay_mobile/models/prediction.dart';
import 'package:agapay_mobile/services/auth_api.dart';
import 'package:agapay_mobile/widgets/common/forecast_panel.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'support/accounts.dart';
import 'support/predictions.dart';

void main() {
  test(
    'contract preserves real zeros and rejects malformed or misleading values',
    () {
      final value = predictionFixture(status: 'available', source: 'model');
      for (final point in value['forecasts'] as List) {
        point['water_depth_cm'] = 0;
      }
      expect(Prediction.fromJson(value).points.first.waterDepthCm, 0);
      expect(
        () => Prediction.fromJson({...value, 'status': 'stale_data'}),
        throwsFormatException,
      );
      expect(
        () => Prediction.fromJson({...value, 'source': 'simulated'}),
        throwsFormatException,
      );
      expect(
        () => Prediction.fromJson({...value, 'forecasts': []}),
        throwsFormatException,
      );
      (value['forecasts'] as List).first['water_depth_cm'] = double.nan;
      expect(() => Prediction.fromJson(value), throwsFormatException);
    },
  );

  test('expired predictions and network failure suppress values', () async {
    var now = DateTime.utc(2026, 9, 4, 12);
    var fail = false;
    final api = AuthApi(
      storage: MemoryTokens(),
      client: MockClient((_) async {
        if (fail) throw http.ClientException('offline');
        return http.Response(
          jsonEncode(
            predictionFixture(status: 'available', source: 'model', now: now),
          ),
          200,
        );
      }),
    );
    final controller = ForecastController(api, now: () => now);
    await controller.setOwner(1);
    expect(controller.available, isTrue);
    now = now.add(const Duration(seconds: 61));
    expect(controller.expired, isTrue);
    expect(controller.available, isFalse);
    fail = true;
    await controller.refresh();
    expect(controller.data, isNull);
    expect(controller.error, contains('Unable to connect'));
    controller.dispose();
    api.dispose();
  });

  test(
    'old preview responses cannot replace actual status or another account',
    () async {
      final delayed = Completer<http.Response>();
      final api = AuthApi(
        storage: MemoryTokens(),
        client: MockClient((request) async {
          if (request.url.queryParameters['mode'] == 'preview') {
            return delayed.future;
          }
          return http.Response(jsonEncode(predictionFixture()), 200);
        }),
      );
      final controller = ForecastController(api);
      await controller.setOwner(1);
      final preview = controller.setPreview(true);
      await controller.setPreview(false);
      delayed.complete(
        http.Response(
          jsonEncode(
            predictionFixture(status: 'available', source: 'simulated'),
          ),
          200,
        ),
      );
      await preview;
      expect(controller.data?.status, 'not_trained');
      expect(controller.preview, isFalse);
      await controller.setOwner(null);
      expect(controller.data, isNull);
      expect(controller.previewAllowed, isFalse);
      controller.dispose();
      api.dispose();
    },
  );

  test('all unavailable states contain no forecast values', () {
    for (final status in forecastLabels.keys.where((s) => s != 'available')) {
      final parsed = Prediction.fromJson(
        predictionFixture(status: status, source: 'simulated'),
      );
      expect(parsed.points.every((p) => p.waterDepthCm == null), isTrue);
    }
  });

  testWidgets(
    'forecast cards show preview states at narrow widths without changing alerts',
    (tester) async {
      tester.view.physicalSize = const Size(320, 700);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final app = fixtureController();
      await app.login('resident@example.com', 'long-password-value');
      await app.forecasts.refresh();
      final alert = app.alert;
      await tester.pumpWidget(
        AppScope(
          controller: app,
          child: const MaterialApp(
            home: Scaffold(body: SingleChildScrollView(child: ForecastPanel())),
          ),
        ),
      );
      await tester.pump();
      expect(find.text('Model not trained'), findsOneWidget);
      expect(find.text('—'), findsNWidgets(3));
      await tester.ensureVisible(find.text('Preview sample scenarios'));
      await tester.tap(find.text('Preview sample scenarios'));
      await tester.pump();
      await tester.pump();
      expect(find.text('SIMULATED PREVIEW'), findsOneWidget);
      expect(find.text('96.0'), findsOneWidget);
      expect(app.alert, alert);
      for (final status in forecastLabels.keys.where((s) => s != 'available')) {
        await app.forecasts.setPreview(true, scenario: status);
        await tester.pump();
        expect(find.text('—'), findsNWidgets(3));
        expect(find.text('96.0'), findsNothing);
        expect(tester.takeException(), isNull);
      }
      await app.forecasts.setPreview(false);
      await tester.pump();
      expect(find.text('Model not trained'), findsOneWidget);
      await tester.pumpWidget(const SizedBox.shrink());
      app.dispose();
    },
  );
}
