import 'dart:async';
import 'dart:convert';
import 'package:agapay_mobile/controllers/delivery_controller.dart';
import 'package:agapay_mobile/services/auth_api.dart';
import 'package:agapay_mobile/services/notification_receipts.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'support/accounts.dart';
import 'package:agapay_mobile/core/ui.dart';
import 'package:agapay_mobile/screens/alerts/delivery_evidence_screen.dart';

class MemoryReceipts implements ReceiptStorage {
  final values = <String, String>{};
  @override
  Future<Map<String, String>> readAll() async => Map.from(values);
  @override
  Future<void> write(String key, String value) async {
    values[key] = value;
  }

  @override
  Future<void> delete(String key) async {
    values.remove(key);
  }
}

final packet = <String, Object?>{
  'type': 'SENSOR_ESCALATION',
  'alert_id': '8',
  'delivery_id': '17',
  'attempt_no': '1',
  'receipt_token': 'a' * 43,
};
AuthApi apiFor(
  Future<http.Response> Function(http.Request) handler, {
  String? origin,
}) => AuthApi(
  baseUrl: origin,
  client: MockClient(handler),
  storage: MemoryTokens(),
  readerStorage: MemoryReaderStorage(),
);
Map<String, dynamic> delivery({int version = 1}) => {
  'id': 17,
  'version': version,
  'receipt_stages': <dynamic>[],
  'can_acknowledge': true,
};
void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  for (final dark in [false, true]) {
    testWidgets(
      'delivery evidence remains usable on a narrow ${dark ? 'dark' : 'light'} screen',
      (tester) async {
        tester.view.physicalSize = const Size(320, 640);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        final app = fixtureController(receiptStorage: MemoryReceipts());
        await app.login('resident@example.com', 'password123');
        await tester.pumpWidget(
          AppScope(
            controller: app,
            child: MaterialApp(
              theme: dark ? AppTheme.dark : AppTheme.light,
              home: const DeliveryEvidenceScreen(),
            ),
          ),
        );
        await tester.pump(const Duration(milliseconds: 100));
        app.deliveries.items = [
          {
            ...delivery(),
            'station_id': 'TEST_STATION',
            'severity': 'WARNING',
            'state': 'SENT',
            'provider_accepted': true,
            'queued_at': '2026-10-22T00:00:00Z',
            'expires_at': '2026-10-22T00:05:00Z',
          },
        ];
        app.notifyListeners();
        await tester.pump();
        expect(
          find.textContaining(
            'Provider acceptance does not confirm phone display',
          ),
          findsOneWidget,
        );
        await tester.scrollUntilVisible(
          find.text('RECEIVED: unknown / not instrumented'),
          150,
        );
        expect(
          find.text('RECEIVED: unknown / not instrumented'),
          findsOneWidget,
        );
        expect(find.text('OPENED: unknown / not instrumented'), findsOneWidget);
        expect(
          find.text('ACKNOWLEDGED: unknown / not instrumented'),
          findsOneWidget,
        );
        expect(tester.takeException(), isNull);
        await tester.pumpWidget(const SizedBox.shrink());
        app.dispose();
      },
    );
  }
  test(
    'offline callback survives a new journal, keeps original time and submits without session authorization',
    () async {
      final storage = MemoryReceipts(), requests = <http.Request>[];
      var offline = true;
      final api = apiFor((request) async {
        requests.add(request);
        if (offline) throw http.ClientException('Offline');
        return http.Response('{}', 201);
      });
      final captured = DateTime.utc(2026, 10, 22, 1);
      final first = NotificationReceiptJournal(
        api,
        storage: storage,
        now: () => captured,
      );
      expect(await first.capture(packet, 'RECEIVED'), true);
      await first.flush();
      expect(first.pending, 1);
      expect(storage.values.length, 1);
      expect(first.warning, contains('unconfirmed'));
      offline = false;
      final restarted = NotificationReceiptJournal(
        api,
        storage: storage,
        now: () => captured.add(const Duration(minutes: 3)),
      );
      await restarted.flush();
      expect(storage.values, isEmpty);
      expect(requests.length, 2);
      for (final request in requests) {
        expect(request.headers.containsKey('authorization'), false);
        final body = jsonDecode(request.body) as Map;
        expect(body['reported_at'], captured.toIso8601String());
        expect(body['stage'], 'RECEIVED');
        expect(body.containsKey('latitude'), false);
      }
      api.dispose();
    },
  );
  test(
    'open evidence never fabricates received or acknowledged stages and duplicate capture keeps original record',
    () async {
      final storage = MemoryReceipts();
      final api = apiFor((_) async => http.Response('{}', 201));
      final journal = NotificationReceiptJournal(api, storage: storage);
      expect(await journal.capture(packet, 'OPENED'), true);
      final original = storage.values.values.single;
      expect(await journal.capture(packet, 'OPENED'), true);
      expect(storage.values.values.single, original);
      expect(await journal.capture(packet, 'ACKNOWLEDGED'), false);
      expect(
        await journal.capture({
          ...packet,
          'receipt_token': 'invalid',
        }, 'RECEIVED'),
        false,
      );
      expect(storage.values.length, 1);
      expect(jsonDecode(original)['stage'], 'OPENED');
      api.dispose();
    },
  );
  test(
    'expired or withdrawn capability is discarded with explicit unrecorded warning',
    () async {
      final storage = MemoryReceipts();
      var calls = 0;
      final api = apiFor((_) async {
        calls++;
        return http.Response('{"detail":"Withdrawn"}', 403);
      });
      final journal = NotificationReceiptJournal(api, storage: storage);
      await journal.capture(packet, 'RECEIVED');
      await journal.flush();
      await journal.flush();
      expect(storage.values, isEmpty);
      expect(calls, 1);
      expect(journal.warning, contains('not recorded'));
      api.dispose();
    },
  );
  test(
    'receipt queues are origin scoped and a full buffer never evicts unexpired callbacks',
    () async {
      final storage = MemoryReceipts();
      var calls = 0;
      final api = apiFor((_) async {
        calls++;
        return http.Response('{}', 201);
      }, origin: 'https://one.example.test');
      final journal = NotificationReceiptJournal(api, storage: storage);
      for (var id = 1; id <= 200; id++) {
        expect(
          await journal.capture({...packet, 'delivery_id': '$id'}, 'RECEIVED'),
          true,
        );
      }
      expect(
        await journal.capture({...packet, 'delivery_id': '201'}, 'RECEIVED'),
        false,
      );
      expect(storage.values.length, 200);
      final other = apiFor((_) async {
        calls++;
        return http.Response('{}', 201);
      }, origin: 'https://two.example.test');
      await NotificationReceiptJournal(other, storage: storage).flush();
      expect(calls, 0);
      expect(storage.values.length, 200);
      api.dispose();
      other.dispose();
    },
  );
  test(
    'acknowledgement conflict is never automatically retried; explicit refresh uses newer displayed version',
    () async {
      final requests = <Map<String, dynamic>>[];
      var version = 1;
      final api = apiFor((request) async {
        if (request.method == 'POST') {
          requests.add(jsonDecode(request.body) as Map<String, dynamic>);
          return http.Response(
            '{"detail":{"message":"Refresh required","current":{"version":2}}}',
            409,
          );
        }
        if (request.url.path.endsWith('/consent')) {
          return http.Response('{"version":0,"enabled":false}', 200);
        }
        return http.Response(
          jsonEncode({
            'items': [delivery(version: version)],
            'next_before_id': null,
          }),
          200,
        );
      });
      final controller = DeliveryController(api, storage: MemoryReceipts())
        ..setOwner(1);
      await controller.refresh();
      await controller.acknowledge(
        17,
        controller.items.single['version'] as int,
      );
      expect(controller.conflicted, true);
      await controller.acknowledge(17, 1);
      expect(requests.length, 1);
      expect(controller.items.single['receipt_stages'], isEmpty);
      version = 2;
      await controller.refresh();
      expect(controller.conflicted, false);
      await controller.acknowledge(
        17,
        controller.items.single['version'] as int,
      );
      expect(requests.last['expected_version'], 2);
      controller.dispose();
      api.dispose();
    },
  );
  test(
    'late delivery read from a previous account cannot populate the new owner',
    () async {
      final delayed = Completer<http.Response>();
      var calls = 0;
      final api = apiFor((request) async {
        calls++;
        return calls == 1
            ? delayed.future
            : http.Response('{"version":0,"enabled":false}', 200);
      });
      final controller = DeliveryController(api, storage: MemoryReceipts())
        ..setOwner(1);
      final read = controller.refresh();
      await Future<void>.delayed(Duration.zero);
      controller.setOwner(2);
      delayed.complete(
        http.Response(
          jsonEncode({
            'items': [delivery()],
            'next_before_id': null,
          }),
          200,
        ),
      );
      await read;
      expect(controller.items, isEmpty);
      expect(controller.consent, isNull);
      controller.dispose();
      api.dispose();
    },
  );
}
