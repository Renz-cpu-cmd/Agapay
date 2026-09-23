import 'dart:async';
import 'dart:convert';
import 'package:agapay_mobile/controllers/app_controller.dart';
import 'package:agapay_mobile/controllers/notification_registration_controller.dart';
import 'package:agapay_mobile/services/auth_api.dart';
import 'package:agapay_mobile/services/push_token_provider.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'support/accounts.dart';

const tokenOne = PushToken(
  token: 'synthetic-test-push-token-one',
  installationId: '00000000-0000-4000-8000-000000000001',
  platform: PushPlatform.android,
);
const tokenTwo = PushToken(
  token: 'synthetic-test-push-token-two',
  installationId: '00000000-0000-4000-8000-000000000001',
  platform: PushPlatform.android,
);

class FakeTokens implements PushTokenProvider {
  final events = StreamController<PushToken?>.broadcast(sync: true);
  PushToken? value = tokenOne;
  Future<PushToken?>? pending;
  int reads = 0;
  @override
  bool get supported => true;
  @override
  Stream<PushToken?> get changes => events.stream;
  @override
  Future<PushToken?> currentToken() async {
    reads++;
    return pending == null ? value : await pending;
  }

  void rotate(PushToken? token) {
    value = token;
    events.add(token);
  }
}

class Harness {
  Harness({bool enabled = true}) {
    api = AuthApi(
      storage: storage,
      client: MockClient((request) async {
        requests.add(request);
        if (request.url.path.startsWith('/api/notification-devices')) {
          final custom = deviceResponse;
          if (custom != null) return await custom(request);
          if (request.method == 'DELETE') return http.Response('', 204);
          return http.Response(
            jsonEncode({'id': 'device-id', 'enabled': true}),
            200,
          );
        }
        if (request.url.path == '/api/auth/logout') {
          return http.Response('', 204);
        }
        if (request.url.path == '/api/auth/me') {
          return http.Response(jsonEncode(resident()), 200);
        }
        if (request.url.path == '/api/auth/login') {
          return http.Response(
            jsonEncode({
              'user': resident(),
              'access_token': 'test-session',
              'expires_at': '2030-01-01T00:00:00Z',
            }),
            200,
          );
        }
        if (request.url.path == '/api/community-alerts' ||
            request.url.path == '/api/community-alerts/active' ||
            request.url.path == '/api/sos') {
          return http.Response('{"items":[],"total":0}', 200);
        }
        if (request.url.path == '/api/monitoring/stations') {
          return http.Response(
            jsonEncode({
              'checked_at': DateTime.now().toUtc().toIso8601String(),
              'stale_after_seconds': 30,
              'stations': [],
            }),
            200,
          );
        }
        return http.Response('{"detail":"Test service unavailable"}', 503);
      }),
    );
    app = AppController(
      authApi: api,
      sosStorage: MemorySosDrafts(),
      pushTokenProvider: enabled ? tokens : null,
    );
  }
  final tokens = FakeTokens();
  final storage = MemoryTokens();
  final requests = <http.Request>[];
  Future<http.Response> Function(http.Request)? deviceResponse;
  late final AuthApi api;
  late final AppController app;
  NotificationRegistrationController get registration =>
      app.notificationRegistration;
  List<http.Request> get deviceRequests => requests
      .where((r) => r.url.path.startsWith('/api/notification-devices'))
      .toList();
  Future<void> login() async {
    await app.login('resident@example.com', 'test-password');
    await registration.settled;
  }

  Future<void> close() async {
    // Drain the immediate monitoring/forecast fixture responses, while any
    // deliberately gated notification request remains pending for its test.
    await Future<void>.delayed(Duration.zero);
    app.dispose();
    await tokens.events.close();
  }
}

void main() {
  test(
    'natural 401 after registration clears API state without revoking push',
    () async {
      final h = Harness();
      addTearDown(h.close);
      await h.login();
      h.deviceResponse = (_) async =>
          http.Response('{"detail":"Expired"}', 401);
      h.tokens.rotate(tokenTwo);
      await h.registration.settled;
      expect(h.app.signedIn, isFalse);
      expect(h.storage.value, isNull);
      expect(h.deviceRequests.map((r) => r.method), ['POST', 'POST']);
      expect(h.requests.any((r) => r.url.path == '/api/auth/logout'), isFalse);
      h.tokens.rotate(null);
      await h.registration.settled;
      expect(h.deviceRequests.length, 2);
    },
  );

  test(
    'explicit logout still revokes when device DELETE reports expired session',
    () async {
      final h = Harness();
      addTearDown(h.close);
      await h.login();
      h.deviceResponse = (_) async =>
          http.Response('{"detail":"Expired"}', 401);
      await h.app.logout();
      expect(h.deviceRequests.last.method, 'DELETE');
      expect(h.requests.last.url.path, '/api/auth/logout');
      expect(h.requests.last.headers['Authorization'], 'Bearer test-session');
      expect(h.storage.value, isNull);
      expect(h.app.signedIn, isFalse);
    },
  );

  test(
    'no registration logged out and default provider makes no requests',
    () async {
      final h = Harness(enabled: false);
      addTearDown(h.close);
      await h.registration.refresh();
      expect(h.deviceRequests, isEmpty);
      await h.login();
      expect(h.deviceRequests, isEmpty);
      expect(h.registration.state, NotificationRegistrationState.disabled);
      expect(h.app.signedIn, isTrue);
    },
  );

  test(
    'authenticated login registers with existing bearer and safe state',
    () async {
      final h = Harness();
      addTearDown(h.close);
      await h.login();
      final request = h.deviceRequests.single;
      expect(request.method, 'POST');
      expect(request.headers['Authorization'], 'Bearer test-session');
      expect(jsonDecode(request.body), tokenOne.registrationBody);
      expect(h.registration.state, NotificationRegistrationState.registered);
      expect(tokenOne.toString(), 'PushToken(redacted)');
      expect(h.registration.toString(), isNot(contains('synthetic-test-push')));
      expect(h.app.communityAlerts.active.error, isNull);
    },
  );

  test(
    'token rotation updates registration and repeated token is deduplicated',
    () async {
      final h = Harness();
      addTearDown(h.close);
      await h.login();
      h.tokens.rotate(tokenTwo);
      await h.registration.settled;
      h.tokens.rotate(tokenTwo);
      await h.registration.settled;
      expect(h.deviceRequests.length, 2);
      expect(jsonDecode(h.deviceRequests.last.body), tokenTwo.registrationBody);
    },
  );

  test('no token waits and later token registers', () async {
    final h = Harness();
    addTearDown(h.close);
    h.tokens.value = null;
    await h.login();
    expect(h.deviceRequests, isEmpty);
    expect(h.registration.state, NotificationRegistrationState.waiting);
    h.tokens.rotate(tokenOne);
    await h.registration.settled;
    expect(h.deviceRequests.length, 1);
  });

  test('token withdrawal removes registration without logout', () async {
    final h = Harness();
    addTearDown(h.close);
    await h.login();
    h.tokens.rotate(null);
    await h.registration.settled;
    expect(h.deviceRequests.last.method, 'DELETE');
    expect(h.app.signedIn, isTrue);
    expect(h.registration.state, NotificationRegistrationState.waiting);
  });

  test(
    'logout removes device before session then ignores token changes',
    () async {
      final h = Harness();
      addTearDown(h.close);
      await h.login();
      await h.app.logout();
      expect(h.deviceRequests.last.method, 'DELETE');
      expect(h.requests.last.url.path, '/api/auth/logout');
      h.tokens.rotate(tokenTwo);
      await h.registration.settled;
      expect(h.deviceRequests.length, 2);
      expect(h.app.signedIn, isFalse);
      expect(h.storage.value, isNull);
      expect(h.registration.state, NotificationRegistrationState.disabled);
    },
  );

  test('failed device cleanup still revokes session', () async {
    final h = Harness();
    addTearDown(h.close);
    await h.login();
    h.deviceResponse = (_) async =>
        http.Response('{"detail":"Unavailable"}', 503);
    await h.app.logout();
    expect(h.requests.last.url.path, '/api/auth/logout');
    expect(h.app.signedIn, isFalse);
  });

  test(
    'registration failure keeps login and can retry without exposing errors',
    () async {
      final h = Harness();
      addTearDown(h.close);
      h.deviceResponse = (_) async =>
          http.Response('{"detail":"synthetic-test-push-token-one"}', 503);
      await h.login();
      expect(h.app.signedIn, isTrue);
      expect(h.storage.value, 'test-session');
      expect(h.registration.state, NotificationRegistrationState.unavailable);
      h.deviceResponse = null;
      await h.registration.refresh();
      expect(h.registration.state, NotificationRegistrationState.registered);
      expect(h.deviceRequests.length, 2);
    },
  );

  test(
    '401 follows AuthApi expiry and clears all resident ownership',
    () async {
      final h = Harness();
      addTearDown(h.close);
      h.deviceResponse = (_) async =>
          http.Response('{"detail":"Expired"}', 401);
      await h.login();
      expect(h.app.signedIn, isFalse);
      expect(h.storage.value, isNull);
      expect(h.registration.state, NotificationRegistrationState.disabled);
      h.tokens.rotate(tokenTwo);
      await h.registration.settled;
      expect(h.deviceRequests.length, 1);
    },
  );

  test('rotation waits for in-flight registration with no overlap', () async {
    final h = Harness();
    addTearDown(h.close);
    final gate = Completer<http.Response>();
    final started = Completer<void>();
    h.deviceResponse = (_) {
      if (!started.isCompleted) started.complete();
      return gate.future;
    };
    await h.app.login('resident@example.com', 'test-password');
    await started.future;
    h.tokens.rotate(tokenTwo);
    await Future<void>.delayed(Duration.zero);
    expect(h.deviceRequests.length, 1);
    h.deviceResponse = null;
    gate.complete(http.Response('{"id":"device-id","enabled":true}', 200));
    await h.registration.settled;
    expect(h.deviceRequests.length, 2);
    expect(jsonDecode(h.deviceRequests.last.body), tokenTwo.registrationBody);
  });

  test('logout drains in-flight registration then deletes it', () async {
    final h = Harness();
    addTearDown(h.close);
    final gate = Completer<http.Response>();
    final started = Completer<void>();
    h.deviceResponse = (_) {
      started.complete();
      return gate.future;
    };
    await h.app.login('resident@example.com', 'test-password');
    await started.future;
    final logout = h.app.logout();
    await Future<void>.delayed(Duration.zero);
    expect(h.requests.any((r) => r.url.path == '/api/auth/logout'), isFalse);
    h.deviceResponse = null;
    gate.complete(http.Response('{"id":"device-id","enabled":true}', 200));
    await logout;
    expect(h.deviceRequests.map((r) => r.method), ['POST', 'DELETE']);
    expect(h.app.signedIn, isFalse);
  });

  test('slow initial token read cannot overwrite newer rotation', () async {
    final h = Harness();
    addTearDown(h.close);
    final tokenRead = Completer<PushToken?>();
    h.tokens.pending = tokenRead.future;
    await h.app.login('resident@example.com', 'test-password');
    h.tokens.rotate(tokenTwo);
    tokenRead.complete(tokenOne);
    await h.registration.settled;
    expect(h.deviceRequests.length, 2);
    expect(jsonDecode(h.deviceRequests.last.body), tokenTwo.registrationBody);
  });

  test(
    'password change clears registration and stops token subscription',
    () async {
      final h = Harness();
      addTearDown(h.close);
      await h.login();
      await h.app.saveProfile({'password': 'new-test-password'});
      h.tokens.rotate(tokenTwo);
      await h.registration.settled;
      expect(h.app.signedIn, isFalse);
      expect(h.registration.state, NotificationRegistrationState.disabled);
      expect(h.deviceRequests.length, 1);
    },
  );

  test('disposal suppresses queued rotations and late responses', () async {
    final h = Harness();
    final tokenRead = Completer<PushToken?>();
    h.tokens.pending = tokenRead.future;
    await h.app.login('resident@example.com', 'test-password');
    h.tokens.rotate(tokenTwo);
    await h.close();
    tokenRead.complete(tokenOne);
    await h.registration.settled;
    expect(h.deviceRequests, isEmpty);
  });

  test(
    'malformed registration and provider errors are safe unavailable states',
    () async {
      final h = Harness();
      addTearDown(h.close);
      h.deviceResponse = (_) async => http.Response('{}', 200);
      await h.login();
      expect(h.registration.state, NotificationRegistrationState.unavailable);
      expect(h.app.signedIn, isTrue);
      h.tokens.events.addError(
        StateError('synthetic-token-must-not-be-displayed'),
      );
      expect(h.registration.state, NotificationRegistrationState.unavailable);
    },
  );
}
