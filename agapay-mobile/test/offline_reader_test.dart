import 'dart:async';
import 'dart:convert';
import 'package:agapay_mobile/controllers/monitoring_controller.dart';
import 'package:agapay_mobile/controllers/sos_controller.dart';
import 'package:agapay_mobile/services/auth_api.dart';
import 'package:agapay_mobile/services/reader_cache.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'support/accounts.dart';
import 'monitoring_contract_test.dart' show retainedStation;

class UnavailableReaderStorage extends MemoryReaderStorage {
  @override
  Future<void> write(String key, String value) async {
    throw StateError('Device key unavailable');
  }
}

class DelayedDiscardStore extends MemorySosDrafts {
  final gate = Completer<void>();
  @override
  Future<void> clear(int owner) async {
    await gate.future;
    await super.clear(owner);
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test(
    'cold offline reader restores original timestamps and blocks writes until explicit verification',
    () async {
      final storage = MemoryReaderStorage(),
          tokens = MemoryTokens()..value = 'private-session';
      final checked = DateTime.now().toUtc().subtract(const Duration(hours: 1));
      var offline = false, posts = 0;
      http.Client client() => MockClient((request) async {
        if (offline) throw http.ClientException('airplane mode');
        if (request.method != 'GET') posts++;
        if (request.url.path.endsWith('/me')) {
          return http.Response(jsonEncode(resident()), 200);
        }
        return http.Response(
          jsonEncode({
            'checked_at': checked.toIso8601String(),
            'stale_after_seconds': 30,
            'stations': [retainedStation(checked)],
          }),
          200,
        );
      });
      var api = AuthApi(
        client: client(),
        storage: tokens,
        readerStorage: storage,
      );
      await api.restore();
      await api.request('monitoring/stations?history_limit=20');
      await Future.wait([
        api.saveReaderState({'history_offset': 50}),
        api.saveReaderState({'last_episode_id': 12}),
      ]);
      api.dispose();
      offline = true;
      api = AuthApi(client: client(), storage: tokens, readerStorage: storage);
      expect((await api.restore())?.id, 1);
      expect(api.offlineReader, isTrue);
      final controller = MonitoringController(api);
      controller.setOwner(1);
      await Future<void>.delayed(const Duration(milliseconds: 30));
      expect(controller.snapshot?.checkedAt, checked.toLocal());
      expect(controller.primary?.currentDepthCm, 105);
      expect(controller.isOnline(controller.primary!), isFalse);
      expect(controller.isFresh(controller.primary!), isFalse);
      expect(
        controller.depthAge(controller.primary!),
        greaterThanOrEqualTo(7200),
      );
      expect(
        await api.restoreReaderState(),
        containsPair('last_episode_id', 12),
      );
      expect(
        await api.restoreReaderState(),
        containsPair('history_offset', 50),
      );
      await expectLater(
        api.request('sos', method: 'POST', body: {}),
        throwsA(isA<AccountException>()),
      );
      expect(posts, 0);
      offline = false;
      await api.me();
      expect(api.offlineReader, isFalse);
      expect(posts, 0);
      controller.dispose();
      api.dispose();
    },
  );

  test(
    '401 and 403 never fall back to a cached authenticated response',
    () async {
      for (final status in [401, 403]) {
        final storage = MemoryReaderStorage(),
            tokens = MemoryTokens()..value = 'private-session';
        var code = 200;
        final api = AuthApi(
          storage: tokens,
          readerStorage: storage,
          client: MockClient(
            (r) async => http.Response(
              jsonEncode(
                code == 200
                    ? (r.url.path.endsWith('/me') ? resident() : {'items': []})
                    : {'detail': 'Denied'},
              ),
              code,
            ),
          ),
        );
        await api.restore();
        await api.request('official-notices?limit=20&offset=0');
        code = status;
        await expectLater(
          api.request('official-notices?limit=20&offset=0'),
          throwsA(isA<AccountException>()),
        );
        expect(api.wasCached('official-notices?limit=20&offset=0'), isFalse);
        if (status == 401) expect(tokens.value, isNull);
        api.dispose();
      }
    },
  );

  test(
    'cache expires physically on access, isolates servers/accounts and bounds storage',
    () async {
      var now = DateTime.utc(2026, 10, 22);
      final storage = MemoryReaderStorage();
      final cache = ReaderCache(
        server: 'https://one.test',
        storage: storage,
        now: () => now,
      );
      await cache.remember('token', resident());
      await cache.put(1, 'monitoring', {
        'depth': 0,
      }, ttl: const Duration(hours: 24));
      expect((await cache.get(1, 'monitoring'))?.data, {'depth': 0});
      expect(await cache.get(2, 'monitoring'), isNull);
      expect(await cache.identity('other-token'), isNull);
      expect(
        await ReaderCache(
          server: 'https://two.test',
          storage: storage,
        ).get(1, 'monitoring'),
        isNull,
      );
      now = now.add(const Duration(hours: 25));
      expect(await cache.get(1, 'monitoring'), isNull);
      expect(jsonDecode(storage.values[cache.ownerKey(1)]!), isEmpty);
      for (var i = 0; i < 40; i++) {
        await cache.put(1, 'notice-$i', {'body': 'x' * 20000});
      }
      final raw = storage.values[cache.ownerKey(1)]!;
      expect(utf8.encode(raw).length, lessThanOrEqualTo(ReaderCache.maxBytes));
      expect((jsonDecode(raw) as Map).length, lessThanOrEqualTo(24));
      await expectLater(
        cache.put(1, 'oversized', 'x' * ReaderCache.maxEntryBytes),
        throwsFormatException,
      );
      expect(await cache.get(1, 'oversized'), isNull);
      await cache.remember('second-token', {...resident(), 'id': 2});
      expect(storage.values[cache.ownerKey(1)], isNull);
      now = now.add(const Duration(days: 8));
      expect(await cache.identity('second-token'), isNull);
      expect(storage.values[cache.identityKey], isNull);
    },
  );

  test(
    'clock rollback and cached staff identity cannot authorize a reader',
    () async {
      var now = DateTime.utc(2026, 10, 22);
      final storage = MemoryReaderStorage();
      final cache = ReaderCache(
        server: 'test',
        storage: storage,
        now: () => now,
      );
      await cache.remember('token', {...resident(), 'role': 'officer'});
      expect(await cache.identity('token'), isNull);
      await cache.remember('token', resident());
      await cache.put(1, 'example', {'zero': 0});
      now = now.subtract(const Duration(hours: 1));
      expect(await cache.get(1, 'example'), isNull);
      expect(await cache.identity('token'), isNull);
    },
  );

  test(
    'outbox survives offline queue restart and sends the original payload only on explicit action',
    () async {
      final storage = MemoryReaderStorage(),
          tokens = MemoryTokens()..value = 'private-session',
          drafts = MemorySosDrafts();
      var offline = false;
      final posts = <Map<String, dynamic>>[];
      final api = AuthApi(
        storage: tokens,
        readerStorage: storage,
        client: MockClient((r) async {
          if (offline) throw http.ClientException('offline');
          if (r.url.path.endsWith('/me')) {
            return http.Response(jsonEncode(resident()), 200);
          }
          if (r.method == 'POST') {
            final body = jsonDecode(r.body) as Map<String, dynamic>;
            posts.add(body);
            return http.Response(jsonEncode(practiceSos(fields: body)), 201);
          }
          return http.Response('{"items":[],"total":0}', 200);
        }),
      );
      await api.restore();
      offline = true;
      await api.restore();
      var controller = SosController(api, storage: drafts);
      await controller.setOwner(1);
      const payload = {
        'location': 'Synthetic saved location',
        'message': 'Practice only',
        'location_source': 'manual',
      };
      await controller.send(payload);
      expect(controller.pendingState, 'queued');
      expect(controller.lastSent, isNull);
      expect(posts, isEmpty);
      final original = Map<String, dynamic>.from(controller.pending!);
      controller.dispose();
      controller = SosController(api, storage: drafts);
      await controller.setOwner(1);
      expect(controller.pending, original);
      offline = false;
      await api.me();
      await controller.refresh();
      expect(posts, isEmpty);
      expect(controller.pendingState, 'queued');
      await controller.send({'location': 'Must not replace original'});
      expect(posts.single, original);
      expect(posts.single.containsKey('_outbox'), isFalse);
      expect(controller.pendingState, 'received');
      controller.dispose();
      controller = SosController(api, storage: drafts);
      await controller.setOwner(1);
      expect(controller.lastSent?.requestId, original['request_id']);
      expect(controller.pending, isNull);
      controller.dispose();
      api.dispose();
    },
  );

  test(
    'UUID-only history never confirms receipt and conflicts never auto-retry or overwrite',
    () async {
      final drafts = MemorySosDrafts();
      Map<String, dynamic>? original;
      var posts = 0, receipt = 'unseen';
      final api = AuthApi(
        storage: MemoryTokens(),
        readerStorage: MemoryReaderStorage(),
        client: MockClient((r) async {
          if (r.url.path.endsWith('/receipt')) {
            return http.Response(
              jsonEncode({'receipt': receipt, 'item': null}),
              200,
            );
          }
          if (r.method == 'POST') {
            posts++;
            original = jsonDecode(r.body) as Map<String, dynamic>;
            throw http.ClientException('response lost');
          }
          return http.Response(
            jsonEncode({
              'items': original == null
                  ? []
                  : [
                      practiceSos(
                        fields: {
                          ...original!,
                          'message': 'Different original payload',
                        },
                      ),
                    ],
              'total': original == null ? 0 : 1,
            }),
            200,
          );
        }),
      );
      var controller = SosController(api, storage: drafts);
      await controller.setOwner(1);
      await controller.send({
        'location': 'Synthetic practice location',
        'message': 'Practice',
        'location_source': 'manual',
      });
      controller.dispose();
      controller = SosController(api, storage: drafts);
      await controller.setOwner(1);
      expect(controller.pendingState, 'unknown');
      expect(controller.lastSent, isNull);
      expect(posts, 1);
      await controller.discardUnsent();
      expect(controller.pending, isNotNull);
      receipt = 'conflict';
      await controller.refresh();
      expect(controller.pendingState, 'conflict');
      await controller.send({'message': 'Overwrite attempt'});
      expect(posts, 1);
      expect(controller.pending, original);
      controller.dispose();
      controller = SosController(api, storage: drafts);
      await controller.setOwner(1);
      expect(controller.pendingState, 'conflict');
      controller.dispose();
      api.dispose();
    },
  );

  test(
    'late success for an old account cannot repopulate its reader cache after logout',
    () async {
      final storage = MemoryReaderStorage(),
          tokens = MemoryTokens()..value = 'private-session';
      final read = Completer<http.Response>();
      final api = AuthApi(
        storage: tokens,
        readerStorage: storage,
        client: MockClient(
          (r) async => r.url.path.endsWith('/me')
              ? http.Response(jsonEncode(resident()), 200)
              : read.future,
        ),
      );
      await api.restore();
      final pending = api.request('official-notices');
      await Future<void>.delayed(Duration.zero);
      await api.clearLocalSession();
      read.complete(http.Response('{"items":[]}', 200));
      await pending;
      expect(storage.values, isEmpty);
      expect(await api.restoreReaderState(), isNull);
      api.dispose();
    },
  );

  test('a rejected retry cannot erase an earlier uncertain send', () async {
    var reject = false;
    final drafts = MemorySosDrafts();
    final api = AuthApi(
      storage: MemoryTokens(),
      readerStorage: MemoryReaderStorage(),
      client: MockClient((r) async {
        if (r.method == 'GET') {
          return http.Response('{"items":[],"total":0}', 200);
        }
        if (reject) return http.Response('{"detail":"Refresh your fix"}', 422);
        throw http.ClientException('lost response');
      }),
    );
    final controller = SosController(api, storage: drafts);
    await controller.setOwner(1);
    await controller.send({
      'location': 'Synthetic practice location',
      'message': 'Practice only',
      'location_source': 'manual',
    });
    final original = Map.from(controller.pending!);
    expect(controller.pendingState, 'unknown');
    reject = true;
    await controller.send({});
    expect(controller.pendingState, 'unknown');
    expect(controller.pending, original);
    await controller.discardUnsent();
    expect(controller.pending, isNotNull);
    controller.dispose();
    api.dispose();
  });

  test(
    'secure storage failure leaves online access usable and reports offline saving unavailable',
    () async {
      final storage = UnavailableReaderStorage();
      final api = AuthApi(
        storage: MemoryTokens()..value = 'private-session',
        readerStorage: storage,
        client: MockClient(
          (r) async => http.Response(
            jsonEncode(r.url.path.endsWith('/me') ? resident() : {'items': []}),
            200,
          ),
        ),
      );
      expect((await api.restore())?.id, 1);
      expect(api.cacheWarning, contains('unavailable'));
      await api.request('official-notices');
      expect(api.cacheWarning, contains('unavailable'));
      expect(storage.values, isEmpty);
      expect(api.offlineReader, isFalse);
      api.dispose();
    },
  );

  test(
    'non-JSON authorization errors preserve their status and never restore cached data',
    () async {
      for (final status in [401, 403]) {
        final cache = MemoryReaderStorage(),
            tokens = MemoryTokens()..value = 'private-session';
        var denied = false;
        final api = AuthApi(
          storage: tokens,
          readerStorage: cache,
          client: MockClient(
            (r) async => denied
                ? http.Response('<html>Denied</html>', status)
                : http.Response(
                    jsonEncode(
                      r.url.path.endsWith('/me') ? resident() : {'items': []},
                    ),
                    200,
                  ),
          ),
        );
        await api.restore();
        await api.request('official-notices');
        denied = true;
        await expectLater(
          api.request('official-notices'),
          throwsA(
            isA<AccountException>().having(
              (e) => e.status,
              'HTTP status',
              status,
            ),
          ),
        );
        expect(api.wasCached('official-notices'), isFalse);
        if (status == 401) {
          expect(cache.values, isEmpty);
          expect(tokens.value, isNull);
        }
        api.dispose();
      }
    },
  );

  test(
    'discard and send cannot race to erase a transmitted reference',
    () async {
      final drafts = DelayedDiscardStore();
      final api = AuthApi(
        storage: MemoryTokens(),
        readerStorage: MemoryReaderStorage(),
        client: MockClient(
          (_) async => http.Response('{"items":[],"total":0}', 200),
        ),
      );
      api.offlineReader = true;
      final controller = SosController(api, storage: drafts);
      await controller.setOwner(1);
      await controller.send({
        'location': 'Synthetic queued practice site',
        'message': 'Practice only',
        'location_source': 'manual',
      });
      final discard = controller.discardUnsent();
      expect(controller.clearing, isTrue);
      expect(await controller.send({}), isNull);
      expect(controller.pendingState, 'queued');
      drafts.gate.complete();
      await discard;
      expect(controller.pending, isNull);
      expect(drafts.values, isEmpty);
      expect(controller.clearing, isFalse);
      controller.dispose();
      api.dispose();
    },
  );

  test(
    'failed monitoring feed cannot revoke a verified session or block an explicit SOS send',
    () async {
      final cache = MemoryReaderStorage(),
          tokens = MemoryTokens()..value = 'private-session';
      var fail = false, posts = 0;
      final api = AuthApi(
        storage: tokens,
        readerStorage: cache,
        client: MockClient((r) async {
          if (r.url.path.endsWith('/me')) {
            return http.Response(jsonEncode(resident()), 200);
          }
          if (r.method == 'POST') {
            posts++;
            return http.Response(
              jsonEncode(
                practiceSos(fields: jsonDecode(r.body) as Map<String, dynamic>),
              ),
              201,
            );
          }
          return fail
              ? http.Response('{}', 503)
              : http.Response('{"items":[]}', 200);
        }),
      );
      await api.restore();
      await api.request('monitoring/stations');
      fail = true;
      await api.request('monitoring/stations');
      expect(api.hasCachedReads, isTrue);
      expect(api.offlineReader, isFalse);
      final receipt = await api.request(
        'sos',
        method: 'POST',
        body: {
          'request_id': '00000000-0000-4000-8000-000000000001',
          'location': 'Synthetic practice entrance',
          'location_source': 'manual',
          'message': 'Practice only',
        },
      );
      expect(receipt['id'], 1);
      expect(posts, 1);
      api.dispose();
    },
  );
}
