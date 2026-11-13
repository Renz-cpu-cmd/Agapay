import 'dart:convert';
import 'package:agapay_mobile/controllers/app_controller.dart';
import 'package:agapay_mobile/controllers/sos_controller.dart';
import 'package:agapay_mobile/models/account.dart';
import 'package:agapay_mobile/services/auth_api.dart';
import 'package:agapay_mobile/widgets/common/sos_response_activity.dart';
import 'package:agapay_mobile/screens/sos/sos_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'support/accounts.dart';

void main() {
  testWidgets(
    'refresh unlocks only an explicit foreground-sharing resume action',
    (tester) async {
      var writes = 0;
      final current = practiceSos(fields: {'location_source': 'manual'});
      final app = AppController(
        locationSource: TestLocationSource(),
        preferenceStorage: MemoryProductPreferences(),
        sosStorage: MemorySosDrafts(),
        authApi: AuthApi(
          readerStorage: MemoryReaderStorage(),
          storage: MemoryTokens(),
          client: MockClient((request) async {
            if (request.method != 'GET') {
              writes++;
            }
            if (request.url.path == '/api/sos') {
              return http.Response(
                jsonEncode({
                  'items': [current],
                  'total': 1,
                }),
                200,
              );
            }
            if (request.url.path == '/api/sos-response/1') {
              return http.Response('{"started":false,"events":[]}', 200);
            }
            return http.Response('{}', 503);
          }),
        ),
      );
      app.user = Account.fromJson(resident());
      app.tab = AppTab.sos;
      await app.sos.setOwner(1);
      app.sos.locationConflicts.add(1);
      await tester.pumpWidget(
        AppScope(
          controller: app,
          child: const MaterialApp(home: Scaffold(body: SosScreen())),
        ),
      );
      await tester.pump(const Duration(milliseconds: 100));
      await tester.ensureVisible(find.text('TEST REQUEST #1'));
      await tester.tap(find.text('TEST REQUEST #1'));
      await tester.pump();
      expect(find.text('Resume foreground sharing'), findsNothing);
      await tester.ensureVisible(
        find.text('Refresh and review location sharing'),
      );
      await tester.tap(find.text('Refresh and review location sharing'));
      await tester.pump();
      await tester.pump();
      expect(find.text('Resume foreground sharing'), findsOneWidget);
      expect(writes, 0);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      app.dispose();
    },
  );
  test(
    'location conflict blocks further fixes until explicit refresh and never replays the rejected fix',
    () async {
      var writes = 0;
      var current = practiceSos(fields: {'location_source': 'manual'});
      final bodies = <Map<String, dynamic>>[];
      final api = AuthApi(
        readerStorage: MemoryReaderStorage(),
        storage: MemoryTokens(),
        client: MockClient((request) async {
          if (request.method == 'GET') {
            return http.Response(
              jsonEncode({
                'items': [current],
                'total': 1,
              }),
              200,
            );
          }
          writes++;
          bodies.add((jsonDecode(request.body) as Map).cast<String, dynamic>());
          if (writes == 1) {
            current = {...current, 'version': 3, 'status': 'ACKNOWLEDGED'};
            return http.Response(
              '{"detail":{"code":"refresh_required","message":"A newer fix exists. Refresh."}}',
              409,
            );
          }
          current = {...current, 'version': 4};
          return http.Response(jsonEncode(current), 200);
        }),
      );
      final controller = SosController(api, storage: MemorySosDrafts());
      await controller.setOwner(1);
      final captured = DateTime.utc(2026, 10, 22, 4);
      Future<dynamic> send(DateTime at) => controller.updateLocation(
        1,
        latitude: 15.97,
        longitude: 120.57,
        accuracyM: 5,
        recordedAt: at,
      );
      expect(await send(captured), isNull);
      expect(controller.locationConflicts, contains(1));
      expect(controller.error, contains('paused'));
      await controller.refresh();
      expect(await send(captured), isNull);
      expect(writes, 1);
      await controller.refresh(manual: true);
      expect(controller.locationConflicts, isEmpty);
      expect(writes, 1);
      await send(captured.add(const Duration(seconds: 20)));
      expect(writes, 2);
      expect(bodies.first['expected_version'], 1);
      expect(bodies.last['expected_version'], 3);
      expect(
        bodies.last['location_recorded_at'],
        isNot(bodies.first['location_recorded_at']),
      );
      controller.dispose();
      api.dispose();
    },
  );

  test('unknown request cannot send a guessed record version', () async {
    var writes = 0;
    final api = AuthApi(
      readerStorage: MemoryReaderStorage(),
      storage: MemoryTokens(),
      client: MockClient((r) async {
        if (r.method != 'GET') {
          writes++;
        }
        return http.Response('{"items":[],"total":0}', 200);
      }),
    );
    final controller = SosController(api, storage: MemorySosDrafts());
    await controller.setOwner(1);
    expect(
      await controller.updateLocation(
        77,
        latitude: 15,
        longitude: 120,
        accuracyM: 5,
        recordedAt: DateTime.now(),
      ),
      isNull,
    );
    expect(writes, 0);
    expect(controller.error, contains('Refresh and review'));
    controller.dispose();
    api.dispose();
  });

  testWidgets(
    'resident sees recorded drill assignment and cached activity is hidden on expiry',
    (tester) async {
      final app = AppController(
        locationSource: TestLocationSource(),
        preferenceStorage: MemoryProductPreferences(),
        sosStorage: MemorySosDrafts(),
        authApi: AuthApi(
          readerStorage: MemoryReaderStorage(),
          storage: MemoryTokens(),
          client: MockClient(
            (request) async => http.Response(
              jsonEncode({
                'mode': 'drill',
                'operational_enabled': false,
                'started': true,
                'phase': 'ASSIGNED',
                'attention': 'needs_review',
                'coordinator_name': 'Drill coordinator',
                'responder_name': 'Drill participant',
                'events': [
                  {
                    'id': 1,
                    'created_at': '2026-10-22T04:00:00Z',
                    'message':
                        'Drill responder assigned; dispatch is not accepted.',
                  },
                ],
              }),
              200,
            ),
          ),
        ),
      );
      app.user = Account.fromJson(resident());
      await tester.pumpWidget(
        AppScope(
          controller: app,
          child: const MaterialApp(
            home: Scaffold(
              body: SingleChildScrollView(child: SosResponseActivity(sosId: 1)),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Recorded stage: ASSIGNED'), findsOneWidget);
      expect(find.textContaining('dispatch is not accepted'), findsOneWidget);
      expect(
        find.text('Drill escalation needs coordinator review.'),
        findsOneWidget,
      );
      app.auth.onExpired?.call();
      await tester.pumpAndSettle();
      expect(find.text('Recorded stage: ASSIGNED'), findsNothing);
      await tester.pumpWidget(const SizedBox.shrink());
      app.dispose();
    },
  );

  testWidgets('missing response feed does not invent a response stage', (
    tester,
  ) async {
    final app = AppController(
      locationSource: TestLocationSource(),
      preferenceStorage: MemoryProductPreferences(),
      sosStorage: MemorySosDrafts(),
      authApi: AuthApi(
        readerStorage: MemoryReaderStorage(),
        storage: MemoryTokens(),
        client: MockClient((_) async => http.Response('{}', 503)),
      ),
    );
    app.user = Account.fromJson(resident());
    await tester.pumpWidget(
      AppScope(
        controller: app,
        child: const MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(child: SosResponseActivity(sosId: 1)),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(
      find.textContaining('Response activity unavailable'),
      findsOneWidget,
    );
    expect(find.textContaining('Recorded stage:'), findsNothing);
    await tester.pumpWidget(const SizedBox.shrink());
    app.dispose();
  });
}
