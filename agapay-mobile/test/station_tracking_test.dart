import 'dart:async';
import 'dart:convert';

import 'package:agapay_mobile/controllers/station_tracking_controller.dart';
import 'package:agapay_mobile/services/auth_api.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'support/accounts.dart';

class FakeSource implements StationPositionSource {
  String? denied;
  final fixes = <TrackingFix>[];
  int requested = 0;
  @override
  Future<String?> ensurePermission() async => denied;
  @override
  Future<TrackingFix> current() async {
    requested++;
    if (fixes.isEmpty) throw StateError('no fix');
    return fixes.removeAt(0);
  }
}

var _fixClock = 0;

/// Each fix is a distinct, increasing GPS time (a real receiver never repeats one).
TrackingFix fix(double accuracy, {double lat = 15.98}) => TrackingFix(
  lat,
  120.56,
  accuracy,
  DateTime.now().toUtc().add(Duration(milliseconds: ++_fixClock)),
);

Map<String, dynamic> session({DateTime? expires}) => {
  'id': 'S1',
  'station_id': 'STATION_001',
  'station_name': 'Portable station',
  'expires_at': (expires ?? DateTime.now().add(const Duration(hours: 1)))
      .toUtc()
      .toIso8601String(),
};

void main() {
  late List<http.Request> posts;
  late List<Map<String, dynamic>> sessions;
  late http.Response Function(http.Request) onPost;

  AuthApi api() {
    final tokens = MemoryTokens()..value = 'token';
    return AuthApi(
      storage: tokens,
      readerStorage: MemoryReaderStorage(),
      client: MockClient((r) async {
        if (r.method == 'GET' && r.url.path == '/api/station-tracking/active') {
          return http.Response(jsonEncode(sessions), 200);
        }
        if (r.method == 'POST' && r.url.path.endsWith('/positions')) {
          posts.add(r);
          return onPost(r);
        }
        return http.Response('{"detail":"unexpected"}', 404);
      }),
    );
  }

  setUp(() {
    posts = [];
    sessions = [session()];
    onPost = (_) => http.Response('{"accepted":true}', 201);
  });

  Future<void> settle() => Future<void>.delayed(const Duration(milliseconds: 30));

  test('loads the assigned session and posts accurate fixes only', () async {
    final source = FakeSource()..fixes.addAll([fix(7.5), fix(80), fix(4)]);
    final controller = StationTrackingController(
      api(),
      source: source,
      interval: const Duration(milliseconds: 40),
    );
    await controller.refresh();
    expect(controller.sessions.single.stationName, 'Portable station');
    await controller.start(controller.sessions.single);
    await Future<void>.delayed(const Duration(milliseconds: 110));
    controller.stop();
    expect(posts.length, 2, reason: 'the ±80 m fix is never uploaded');
    final body = jsonDecode(posts.first.body) as Map<String, dynamic>;
    expect(body.keys.toSet(), {'latitude', 'longitude', 'accuracy_m', 'captured_at'});
    expect(body['accuracy_m'], 7.5);
    expect(DateTime.parse(body['captured_at'] as String).isUtc, isTrue);
    expect(posts.first.url.path, '/api/station-tracking/S1/positions');
    expect((controller.accepted, controller.rejected), (2, 1));
    expect(controller.tracking, isFalse);
    controller.dispose();
  });

  test('a repeated cached fix is neither uploaded nor counted as skipped', () async {
    final same = fix(6);
    final source = FakeSource()..fixes.addAll([same, same, fix(5)]);
    final controller = StationTrackingController(
      api(),
      source: source,
      interval: const Duration(milliseconds: 40),
    );
    await controller.refresh();
    await controller.start(controller.sessions.single);
    await Future<void>.delayed(const Duration(milliseconds: 110));
    controller.stop();
    expect(posts.length, 2);
    expect((controller.accepted, controller.rejected), (2, 0));
    controller.dispose();
  });

  test('denied permission never starts reporting', () async {
    final source = FakeSource()..denied = 'Precise location permission is needed.';
    final controller = StationTrackingController(api(), source: source);
    await controller.refresh();
    await controller.start(controller.sessions.single);
    expect(controller.tracking, isFalse);
    expect(controller.message, contains('permission'));
    expect(source.requested, 0);
    controller.dispose();
  });

  test('an ended session stops reporting; a stale fix only skips', () async {
    var calls = 0;
    onPost = (_) => ++calls == 1
        ? http.Response('{"detail":"GPS fix is not newer than the last accepted fix"}', 409)
        : http.Response('{"detail":"Tracking session is not active"}', 409);
    final source = FakeSource()..fixes.addAll([fix(5), fix(5), fix(5)]);
    final controller = StationTrackingController(
      api(),
      source: source,
      interval: const Duration(milliseconds: 30),
    );
    await controller.refresh();
    await controller.start(controller.sessions.single);
    await settle();
    expect(controller.tracking, isTrue, reason: 'not-newer fix is skipped');
    await Future<void>.delayed(const Duration(milliseconds: 60));
    expect(controller.tracking, isFalse);
    expect(controller.message, contains('no longer active'));
    final after = posts.length;
    await Future<void>.delayed(const Duration(milliseconds: 80));
    expect(posts.length, after);
    controller.dispose();
  });

  test('an expired session stops without posting', () async {
    sessions = [session(expires: DateTime.now().subtract(const Duration(seconds: 1)))];
    final source = FakeSource()..fixes.add(fix(5));
    final controller = StationTrackingController(api(), source: source);
    await controller.refresh();
    await controller.start(controller.sessions.single);
    await settle();
    expect(posts, isEmpty);
    expect(controller.tracking, isFalse);
    expect(controller.message, contains('expired'));
    controller.dispose();
  });

  test('a session time without an offset is UTC, not device local time', () {
    final later = DateTime.now().toUtc().add(const Duration(hours: 4));
    final naive = later.toIso8601String().replaceFirst('Z', '');
    final parsed = TrackingSession.fromJson({...session(), 'expires_at': naive});
    expect(parsed.expiresAt!.difference(later).inSeconds.abs(), lessThan(1));
    final offset = TrackingSession.fromJson({...session(), 'expires_at': '2026-11-13T10:44:04+00:00'});
    expect(offset.expiresAt, DateTime.utc(2026, 11, 13, 10, 44, 4));
  });

  test('a session revoked by an administrator stops on refresh', () async {
    final source = FakeSource()..fixes.addAll(List.generate(5, (_) => fix(5)));
    final controller = StationTrackingController(
      api(),
      source: source,
      interval: const Duration(seconds: 10),
    );
    await controller.refresh();
    await controller.start(controller.sessions.single);
    await settle();
    sessions = [];
    await controller.refresh();
    expect(controller.tracking, isFalse);
    expect(controller.sessions, isEmpty);
    controller.dispose();
  });

  test('reset on sign-out drops sessions and ignores an in-flight fix', () async {
    final pending = Completer<http.Response>();
    final source = FakeSource()..fixes.add(fix(5));
    final controller = StationTrackingController(
      api(),
      source: source,
      interval: const Duration(seconds: 10),
    );
    onPost = (_) => http.Response('{}', 201);
    await controller.refresh();
    final start = controller.start(controller.sessions.single);
    controller.reset();
    await start;
    await settle();
    expect(controller.tracking, isFalse);
    expect(controller.sessions, isEmpty);
    expect(controller.accepted, 0);
    pending.complete(http.Response('{}', 201));
    controller.dispose();
  });
}
