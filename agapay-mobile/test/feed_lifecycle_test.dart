import 'dart:async';
import 'dart:convert';
import 'package:agapay_mobile/controllers/monitoring_controller.dart';
import 'package:agapay_mobile/controllers/hybrid_projection_controller.dart';
import 'package:agapay_mobile/services/auth_api.dart';
import 'package:agapay_mobile/services/reader_cache.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'support/accounts.dart';
import 'support/hybrid_projection.dart';
import 'monitoring_contract_test.dart' show retainedStation;

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  testWidgets(
    'monitoring pauses timers, rejects a late response and refreshes on resume',
    (tester) async {
      final at = DateTime.now().toUtc(), delayed = Completer<http.Response>();
      var calls = 0;
      final queries = <String?>[];
      final api = AuthApi(
        storage: MemoryTokens(),
        readerStorage: MemoryReaderStorage(),
        client: MockClient((r) async {
          calls++;
          queries.add(r.url.queryParameters['history_limit']);
          if (calls == 1) return delayed.future;
          return http.Response(
            jsonEncode({
              'checked_at': at.toIso8601String(),
              'stale_after_seconds': 30,
              'stations': [retainedStation(at)],
            }),
            200,
          );
        }),
      );
      final feed = MonitoringController(api);
      feed.setOwner(1);
      await tester.pump();
      expect(calls, 1);
      feed.setForeground(false);
      delayed.complete(http.Response('{}', 200));
      await tester.pump();
      await tester.pump(const Duration(minutes: 2));
      expect(calls, 1);
      expect(feed.snapshot, isNull);
      feed.setForeground(true);
      await tester.pumpAndSettle();
      expect(calls, 2);
      expect(queries, ['20', '20']);
      expect(feed.snapshot?.checkedAt, at.toLocal(), reason: feed.error);
      feed.setForeground(false);
      await tester.pump(const Duration(minutes: 1));
      expect(calls, 2);
      expect(feed.snapshot?.checkedAt, at.toLocal(), reason: feed.error);
      expect(feed.isOnline(feed.primary!), false);
      feed.dispose();
      api.dispose();
    },
  );
  testWidgets(
    'hybrid background retains its deadline and resumes with one fresh read',
    (tester) async {
      var calls = 0;
      final at = DateTime.now().toUtc();
      final api = AuthApi(
        storage: MemoryTokens(),
        readerStorage: MemoryReaderStorage(),
        client: MockClient((r) async {
          calls++;
          return http.Response(jsonEncode(rainActivityFixture(at: at)), 200);
        }),
      );
      final feed = HybridProjectionController(api, now: () => at);
      feed.setOwner(1);
      await tester.pump();
      await tester.pump();
      expect(feed.gaugeFresh, true);
      final before = calls;
      feed.setForeground(false);
      await tester.pump(const Duration(minutes: 1));
      expect(calls, before);
      expect(feed.available, false);
      feed.setForeground(true);
      await tester.pump();
      await tester.pump();
      expect(calls, before + 1);
      expect(feed.gaugeFresh, true);
      feed.dispose();
      api.dispose();
    },
  );
  test(
    'smaller monitoring reads restore legacy encrypted entries without extending retention',
    () async {
      var at = DateTime.utc(2026, 10, 22);
      final cache = ReaderCache(
        server: 'https://synthetic.example',
        storage: MemoryReaderStorage(),
        now: () => at,
      );
      await cache.put(1, 'monitoring/stations?history_limit=120', {
        'checked_at': at.toIso8601String(),
        'stations': [],
      });
      final original = await cache.get(
        1,
        'monitoring/stations?history_limit=120',
      );
      at = at.add(const Duration(hours: 1));
      final restored = await cache.get(
        1,
        'monitoring/stations?history_limit=20',
      );
      expect(restored?.savedAt, original?.savedAt);
      expect(restored?.data, original?.data);
      expect(
        await cache.get(2, 'monitoring/stations?history_limit=20'),
        isNull,
      );
      at = at.add(const Duration(days: 8));
      expect(
        await cache.get(1, 'monitoring/stations?history_limit=20'),
        isNull,
      );
    },
  );
}
