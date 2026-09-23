import 'dart:async';
import 'dart:convert';
import 'package:agapay_mobile/app.dart';
import 'package:agapay_mobile/controllers/app_controller.dart';
import 'package:agapay_mobile/controllers/notification_registration_controller.dart';
import 'package:agapay_mobile/services/auth_api.dart';
import 'package:agapay_mobile/services/firebase_push.dart';
import 'package:agapay_mobile/services/push_messaging.dart';
import 'package:agapay_mobile/services/push_token_provider.dart';
import 'package:agapay_mobile/navigation/app_routes.dart';
import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'support/accounts.dart';
import 'support/community_alerts.dart';

const validPush = <String, Object?>{
  'type': 'SENSOR_ESCALATION',
  'alert_id': '501',
};

class MemoryPushStore implements PushLocalStore {
  final values = <String, String>{};
  @override
  Future<String?> read(String key) async => values[key];
  @override
  Future<void> write(String key, String value) async {
    values[key] = value;
  }
}

class FakeMessaging implements MessagingGateway {
  PushPermission status = PushPermission.allowed;
  PushPermission response = PushPermission.allowed;
  String? value = 'synthetic-fcm-token';
  int prompts = 0;
  int reads = 0;
  Map<String, Object?>? initial;
  final rotations = StreamController<String>.broadcast(sync: true);
  final foregroundEvents = StreamController<Map<String, Object?>>.broadcast(
    sync: true,
  );
  final openEvents = StreamController<Map<String, Object?>>.broadcast(
    sync: true,
  );
  @override
  Future<PushPermission> permission() async => status;
  @override
  Future<PushPermission> requestPermission() async {
    prompts++;
    return status = response;
  }

  @override
  Future<String?> token() async {
    reads++;
    return value;
  }

  @override
  Stream<String> get tokenChanges => rotations.stream;
  @override
  Stream<Map<String, Object?>> get foreground => foregroundEvents.stream;
  @override
  Stream<Map<String, Object?>> get opened => openEvents.stream;
  @override
  Future<Map<String, Object?>?> initialMessage() async => initial;
  Future<void> close() async {
    await rotations.close();
    await foregroundEvents.close();
    await openEvents.close();
  }
}

Future<void> flush() => Future<void>.delayed(const Duration(milliseconds: 25));

class PushHarness {
  PushHarness({
    bool restored = false,
    Map<String, Object?>? initial,
    this.restoreGate,
  }) {
    gateway.initial = initial;
    if (restored) storage.value = 'synthetic-api-session';
    final api = AuthApi(
      storage: storage,
      client: MockClient((request) async {
        requests.add(request);
        final path = request.url.path;
        if (path == '/api/auth/me') {
          if (restoreGate != null) await restoreGate!.future;
          return http.Response(jsonEncode(resident()), 200);
        }
        if (path == '/api/auth/login') {
          return http.Response(
            jsonEncode({
              'user': resident(),
              'access_token': 'synthetic-api-session',
              'expires_at': '2030-01-01T00:00:00Z',
            }),
            200,
          );
        }
        if (path == '/api/auth/logout' || request.method == 'DELETE') {
          return http.Response('', 204);
        }
        if (path == '/api/notification-devices') {
          return http.Response('{"id":"device-test","enabled":true}', 200);
        }
        if (path == '/api/community-alerts/501') {
          return http.Response(jsonEncode(communityDetail()), detailStatus);
        }
        if (path.startsWith('/api/community-alerts') || path == '/api/sos') {
          return http.Response('{"items":[],"total":0}', 200);
        }
        return http.Response('{"detail":"Test unavailable"}', 503);
      }),
    );
    app = AppController(
      authApi: api,
      sosStorage: MemorySosDrafts(),
      pushTokenProvider: provider,
      pushMessages: gateway,
    );
  }
  final gateway = FakeMessaging();
  final store = MemoryPushStore();
  final storage = MemoryTokens();
  final requests = <http.Request>[];
  final Completer<void>? restoreGate;
  int detailStatus = 200;
  late final provider = FirebasePushTokenProvider(
    gateway,
    platform: PushPlatform.android,
    store: store,
  );
  late final AppController app;
  List<http.Request> get registrations =>
      requests.where((r) => r.url.path == '/api/notification-devices').toList();
  List<http.Request> get details =>
      requests.where((r) => r.url.path == '/api/community-alerts/501').toList();
  Future<void> login() async {
    await app.login('test@example.com', 'test');
    await app.notificationRegistration.settled;
    await flush();
  }

  Future<void> close() async {
    app.dispose();
    await gateway.close();
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('tap returns from history subroute to real episode detail', (
    tester,
  ) async {
    final h = PushHarness(restored: true);
    await tester.pumpWidget(AgapayApp(controller: h.app));
    await tester.pump(const Duration(seconds: 3));
    await tester.pumpAndSettle();
    final navigator = tester.state<NavigatorState>(
      find.byType(Navigator).first,
    );
    unawaited(navigator.pushNamed(AppRoutes.notificationHistory));
    await tester.pumpAndSettle();
    h.gateway.openEvents.add(validPush);
    await tester.pumpAndSettle();
    expect(h.app.communityAlerts.selectedId, 501);
    expect(find.text('Community Test Station'), findsWidgets);
    expect(h.details.length, 1);
    await tester.pumpWidget(const SizedBox.shrink());
    await h.gateway.close();
  });

  test(
    'expired API session on tap clears local state without withdrawing push',
    () async {
      final h = PushHarness();
      addTearDown(h.close);
      await h.login();
      h.detailStatus = 401;
      h.gateway.openEvents.add(validPush);
      await flush();
      expect(h.app.signedIn, isFalse);
      expect(h.app.communityAlerts.detail.data, isNull);
      expect(h.requests.where((r) => r.method == 'DELETE'), isEmpty);
    },
  );

  test(
    'real token adapter registers through AuthApi and rotates same installation',
    () async {
      final h = PushHarness();
      addTearDown(h.close);
      await flush();
      expect(h.registrations, isEmpty);
      await h.login();
      final first =
          jsonDecode(h.registrations.single.body) as Map<String, dynamic>;
      expect(first['provider_token'], 'synthetic-fcm-token');
      expect(first['provider'], 'fcm');
      expect(
        first['installation_id'],
        matches(
          RegExp(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
          ),
        ),
      );
      h.gateway.rotations.add('rotated-test-token');
      await flush();
      await h.app.notificationRegistration.settled;
      final next =
          jsonDecode(h.registrations.last.body) as Map<String, dynamic>;
      expect(next['provider_token'], 'rotated-test-token');
      expect(next['installation_id'], first['installation_id']);
      final restarted = FirebasePushTokenProvider(
        h.gateway,
        platform: PushPlatform.android,
        store: h.store,
      );
      expect(
        (await restarted.currentToken())!.installationId,
        first['installation_id'],
      );
      expect(
        (await h.provider.currentToken()).toString(),
        'PushToken(redacted)',
      );
      await h.app.logout();
      expect(h.requests.any((r) => r.method == 'DELETE'), isTrue);
      h.gateway.rotations.add('after-logout');
      await flush();
      expect(h.registrations.length, 2);
    },
  );

  test(
    'denied permission prompts once, keeps login and waits without registering',
    () async {
      final h = PushHarness();
      addTearDown(h.close);
      h.gateway.status = PushPermission.notDetermined;
      h.gateway.response = PushPermission.denied;
      await h.login();
      await h.app.notificationRegistration.refresh();
      expect(h.gateway.prompts, 1);
      expect(h.gateway.reads, 0);
      expect(h.registrations, isEmpty);
      expect(h.app.signedIn, isTrue);
      expect(
        h.app.notificationRegistration.state,
        NotificationRegistrationState.waiting,
      );
      h.gateway.status = PushPermission.allowed;
      await h.app.notificationRegistration.refresh();
      expect(h.registrations.length, 1);
    },
  );

  test('null token waits without fake registration', () async {
    final h = PushHarness();
    addTearDown(h.close);
    h.gateway.value = null;
    await h.login();
    expect(h.registrations, isEmpty);
    expect(
      h.app.notificationRegistration.state,
      NotificationRegistrationState.waiting,
    );
  });

  test(
    'disabled and failed initialization never require Firebase services',
    () async {
      debugDefaultTargetPlatformOverride = TargetPlatform.android;
      addTearDown(() => debugDefaultTargetPlatformOverride = null);
      var calls = 0;
      Future<void> unavailable() async {
        calls++;
        throw StateError('private SDK error');
      }

      final disabled = await FirebasePushRuntime.initialize(
        enabled: false,
        initializeFirebase: unavailable,
      );
      expect(disabled.provider.supported, isFalse);
      expect(calls, 0);
      final failed = await FirebasePushRuntime.initialize(
        enabled: true,
        initializeFirebase: unavailable,
      );
      expect(failed.provider.supported, isFalse);
      expect(failed.messages, isNull);
      expect(calls, 1);
    },
  );

  test(
    'successful initialization supplies production token adapter through fake SDK',
    () async {
      debugDefaultTargetPlatformOverride = TargetPlatform.android;
      addTearDown(() => debugDefaultTargetPlatformOverride = null);
      final gateway = FakeMessaging();
      addTearDown(gateway.close);
      final runtime = await FirebasePushRuntime.initialize(
        enabled: true,
        initializeFirebase: () async {},
        gatewayFactory: (_) => gateway,
      );
      expect(runtime.provider, isA<FirebasePushTokenProvider>());
      expect(runtime.messages, same(gateway));
    },
  );

  test(
    'foreground valid push refreshes API; malformed push is ignored',
    () async {
      final h = PushHarness();
      addTearDown(h.close);
      await h.login();
      final before = h.requests.length;
      h.gateway.foregroundEvents.add({'type': 'OTHER', 'alert_id': '501'});
      await flush();
      expect(h.requests.length, before);
      h.gateway.foregroundEvents.add(validPush);
      await flush();
      expect(
        h.requests
            .skip(before)
            .where((r) => r.url.path.startsWith('/api/community-alerts'))
            .length,
        2,
      );
      expect(h.app.details, isFalse);
    },
  );

  test(
    'tap fetches authoritative sanitized detail and handles API failure',
    () async {
      final h = PushHarness();
      addTearDown(h.close);
      await h.login();
      h.gateway.openEvents.add(validPush);
      await flush();
      expect(h.details.length, 1);
      expect(h.app.communityAlerts.selectedId, 501);
      expect(h.app.communityAlerts.detail.data?.episode.id, 501);
      h.detailStatus = 503;
      h.gateway.openEvents.add(validPush);
      await flush();
      expect(
        h.app.communityAlerts.detail.error,
        'Alert service is currently unavailable.',
      );
      expect(h.app.communityAlerts.detail.data, isNull);
    },
  );

  test('terminated-start tap waits for restored resident session', () async {
    final gate = Completer<void>();
    final h = PushHarness(
      restored: true,
      initial: validPush,
      restoreGate: gate,
    );
    addTearDown(h.close);
    await flush();
    expect(h.details, isEmpty);
    expect(h.app.signedIn, isFalse);
    gate.complete();
    await h.app.restoreSession();
    await flush();
    expect(h.app.signedIn, isTrue);
    expect(h.details.length, 1);
    expect(h.app.details, isTrue);
  });

  test('logged-out initial and resumed taps expose no alert data', () async {
    final h = PushHarness(initial: validPush);
    addTearDown(h.close);
    await flush();
    h.gateway.openEvents.add(validPush);
    await flush();
    expect(h.details, isEmpty);
    expect(h.app.details, isFalse);
    expect(h.registrations, isEmpty);
  });

  test('payload parser rejects arbitrary navigation and malformed IDs', () {
    for (final id in <Object?>[
      null,
      501,
      '-1',
      '0',
      '../501',
      '1.0',
      ' 501',
      '99999999999999999999',
    ]) {
      expect(
        SensorPush.parse({'type': 'SENSOR_ESCALATION', 'alert_id': id}),
        isNull,
      );
    }
    expect(SensorPush.parse(validPush)?.alertId, 501);
  });
}
