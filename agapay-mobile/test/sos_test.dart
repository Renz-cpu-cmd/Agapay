import 'dart:async';
import 'dart:convert';
import 'package:agapay_mobile/controllers/app_controller.dart';
import 'package:agapay_mobile/controllers/sos_controller.dart';
import 'package:agapay_mobile/screens/sos/sos_screen.dart';
import 'package:agapay_mobile/services/auth_api.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'support/accounts.dart';

http.Response page(List<Map<String, dynamic>> items) =>
    http.Response(jsonEncode({'items': items, 'total': items.length}), 200);
http.Response saved(Map<String, dynamic> fields) =>
    http.Response(jsonEncode(practiceSos(fields: fields)), 201);
const fields = {
  'location': 'Practice site, San Vicente',
  'message': 'Practice only',
  'location_source': 'manual',
};

void main() {
  test(
    'failed send keeps its reference across restart and retry uses identical details',
    () async {
      final drafts = MemorySosDrafts();
      final posts = <String>[];
      var fail = true;
      var status = 'ACTIVE';
      Map<String, dynamic>? record;
      final api = AuthApi(
        storage: MemoryTokens()..value = 'resident-session',
        client: MockClient((request) async {
          if (request.url.path.endsWith('/me')) {
            return http.Response(jsonEncode(resident()), 200);
          }
          expect(request.headers['Authorization'], 'Bearer resident-session');
          if (request.method == 'POST') {
            expect(
              drafts.values[1],
              isNotNull,
              reason: 'Reference must be saved before transmission',
            );
            posts.add(request.body);
            if (fail) throw http.ClientException('connection lost');
            record = jsonDecode(request.body) as Map<String, dynamic>;
            return saved(record!);
          }
          return page(
            record == null
                ? []
                : [practiceSos(fields: record!, status: status)],
          );
        }),
      );
      await api.restore();
      var controller = SosController(api, storage: drafts);
      await controller.setOwner(1);
      expect(await controller.send(fields), isNull);
      expect(controller.lastSent, isNull);
      expect(controller.error, contains('Receipt is unconfirmed'));
      final reference = controller.pending!['request_id'];
      controller.dispose();
      controller = SosController(api, storage: drafts);
      await controller.setOwner(1);
      expect(controller.pending!['request_id'], reference);
      fail = false;
      expect(
        (await controller.send({
          'location': 'Must not replace saved details',
        }))?.id,
        1,
      );
      expect(posts[0], posts[1]);
      expect(controller.pending, isNull);
      expect(drafts.values, isEmpty);
      status = 'ACKNOWLEDGED';
      await controller.refresh();
      expect(controller.lastSent?.acknowledgedBy, 'Test Officer');
      status = 'RESOLVED';
      await controller.refresh();
      expect(controller.lastSent?.resolutionNote, 'Practice complete.');
      await controller.setOwner(null);
      expect(controller.items, isEmpty);
      expect(controller.lastSent, isNull);
      controller.dispose();
      api.dispose();
    },
  );

  test(
    'accepted request with lost response is recovered from history without another POST',
    () async {
      final drafts = MemorySosDrafts();
      Map<String, dynamic>? record;
      var posts = 0;
      final api = AuthApi(
        storage: MemoryTokens(),
        client: MockClient((request) async {
          if (request.method == 'POST') {
            posts++;
            record = jsonDecode(request.body) as Map<String, dynamic>;
            throw http.ClientException('response lost');
          }
          return page(record == null ? [] : [practiceSos(fields: record!)]);
        }),
      );
      var controller = SosController(api, storage: drafts);
      await controller.setOwner(1);
      await controller.send(fields);
      controller.dispose();
      controller = SosController(api, storage: drafts);
      await controller.setOwner(1);
      expect(controller.lastSent?.id, 1);
      expect(controller.pending, isNull);
      expect(posts, 1);
      expect(drafts.values, isEmpty);
      controller.dispose();
      api.dispose();
    },
  );

  test('validation rejection is unsent and allows corrected details', () async {
    final drafts = MemorySosDrafts();
    final api = AuthApi(
      storage: MemoryTokens(),
      client: MockClient(
        (request) async => request.method == 'GET'
            ? page([])
            : http.Response('{"detail":"Refresh GPS location"}', 422),
      ),
    );
    final controller = SosController(api, storage: drafts);
    await controller.setOwner(1);
    expect(await controller.send(fields), isNull);
    expect(controller.error, contains('not accepted'));
    expect(controller.pending, isNull);
    expect(controller.lastSent, isNull);
    expect(drafts.values, isEmpty);
    controller.dispose();
    api.dispose();
  });

  test(
    'old history response cannot overwrite a successful send or another account',
    () async {
      final oldRead = Completer<http.Response>();
      var reads = 0;
      final api = AuthApi(
        storage: MemoryTokens(),
        client: MockClient((request) async {
          if (request.method == 'POST') {
            return saved(jsonDecode(request.body) as Map<String, dynamic>);
          }
          reads++;
          return reads == 2 ? oldRead.future : page([]);
        }),
      );
      final controller = SosController(api, storage: MemorySosDrafts());
      await controller.setOwner(1);
      final refresh = controller.refresh();
      await controller.send(fields);
      oldRead.complete(page([]));
      await refresh;
      expect(controller.items.single.id, 1);
      await controller.setOwner(2);
      expect(controller.items, isEmpty);
      expect(controller.lastSent, isNull);
      controller.dispose();
      api.dispose();
    },
  );

  test(
    'foreground fix updates the open request and sends only GPS fields',
    () async {
      final captured = DateTime.utc(2026, 9, 5, 2, 15);
      final original = practiceSos(fields: fields);
      final api = AuthApi(
        storage: MemoryTokens(),
        client: MockClient((request) async {
          if (request.method == 'GET') return page([original]);
          expect(request.method, 'PATCH');
          expect(request.url.path, '/api/sos/1/location');
          expect(jsonDecode(request.body), {
            'latitude': 15.9792,
            'longitude': 120.571,
            'accuracy_m': 6.5,
            'location_recorded_at': captured.toIso8601String(),
          });
          return http.Response(
            jsonEncode(
              practiceSos(
                fields: {
                  ...fields,
                  'latitude': 15.9792,
                  'longitude': 120.571,
                  'location_source': 'gps',
                  'accuracy_m': 6.5,
                  'location_recorded_at': captured.toIso8601String(),
                },
              ),
            ),
            200,
          );
        }),
      );
      final controller = SosController(api, storage: MemorySosDrafts());
      await controller.setOwner(1);
      final updated = await controller.updateLocation(
        1,
        latitude: 15.9792,
        longitude: 120.571,
        accuracyM: 6.5,
        recordedAt: captured,
      );
      expect(updated?.locationSource, 'gps');
      expect(updated?.accuracyM, 6.5);
      expect(controller.items.single.latitude, 15.9792);
      controller.dispose();
      api.dispose();
    },
  );

  testWidgets(
    'SOS waits for acceptance, shows failure and retries without duplicate submission',
    (tester) async {
      tester.view.physicalSize = const Size(320, 568);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final response = Completer<http.Response>();
      var posts = 0;
      final app = AppController(
        sosStorage: MemorySosDrafts(),
        authApi: AuthApi(
          storage: MemoryTokens(),
          client: MockClient((request) async {
            if (request.url.path.endsWith('/login')) {
              return http.Response(
                jsonEncode({'user': resident(), 'access_token': 'test'}),
                200,
              );
            }
            if (request.method == 'GET') return page([]);
            posts++;
            if (posts == 1) return response.future;
            return saved(jsonDecode(request.body) as Map<String, dynamic>);
          }),
        ),
      );
      await app.login('resident@example.com', 'long-password-value');
      await app.sos.setOwner(1);
      app.navigate(AppTab.sos);
      await tester.pumpWidget(
        AppScope(
          controller: app,
          child: const MaterialApp(home: Scaffold(body: SosScreen())),
        ),
      );
      await tester.pump(const Duration(milliseconds: 400));
      await tester.ensureVisible(
        find.bySemanticsLabel(RegExp('Start practice SOS')),
      );
      await tester.tap(find.bySemanticsLabel(RegExp('Start practice SOS')));
      await tester.pump();
      await tester.enterText(
        find.byKey(const ValueKey('sos-location')),
        'Practice site, San Vicente',
      );
      await tester.ensureVisible(find.text('SEND PRACTICE SOS'));
      await tester.tap(find.text('SEND PRACTICE SOS'));
      await tester.pump();
      expect(find.text('SENDING…'), findsOneWidget);
      expect(find.text('REQUEST RECEIVED'), findsNothing);
      expect(posts, 1);
      await tester.ensureVisible(find.text('BACK TO HISTORY'));
      await tester.tap(find.text('BACK TO HISTORY'));
      await tester.pump();
      expect(find.text('SENDING…'), findsOneWidget);
      response.completeError(http.ClientException('offline'));
      await tester.pump();
      await tester.pump();
      expect(find.textContaining('Receipt is unconfirmed'), findsOneWidget);
      expect(find.text('REQUEST RECEIVED'), findsNothing);
      await tester.ensureVisible(find.text('RETRY SAME REQUEST'));
      await tester.tap(find.text('RETRY SAME REQUEST'));
      await tester.pump();
      await tester.pump();
      expect(find.text('REQUEST RECEIVED'), findsOneWidget);
      expect(posts, 2);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      app.dispose();
    },
  );
}
