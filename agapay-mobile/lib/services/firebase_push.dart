import 'dart:math';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'push_messaging.dart';
import 'push_token_provider.dart';

enum PushPermission { notDetermined, denied, allowed }

/// Injectable SDK boundary: tests never initialize Firebase or contact Google.
abstract interface class MessagingGateway implements PushMessages {
  Future<PushPermission> permission();
  Future<PushPermission> requestPermission();
  Future<String?> token();
  Stream<String> get tokenChanges;
}

abstract interface class PushLocalStore {
  Future<String?> read(String key);
  Future<void> write(String key, String value);
}

class SecurePushStore implements PushLocalStore {
  const SecurePushStore();
  static const _storage = FlutterSecureStorage();
  @override
  Future<String?> read(String key) => _storage.read(key: key);
  @override
  Future<void> write(String key, String value) =>
      _storage.write(key: key, value: value);
}

class FirebasePushTokenProvider implements PushTokenProvider {
  FirebasePushTokenProvider(
    this.gateway, {
    required this.platform,
    PushLocalStore store = const SecurePushStore(),
  }) : _store = store;
  final MessagingGateway gateway;
  final PushPlatform platform;
  final PushLocalStore _store;
  Future<String>? _identity;
  @override
  bool get supported => true;

  Future<String> _installationId() => _identity ??= _loadIdentity();
  Future<String> _loadIdentity() async {
    const key = 'agapay_push_installation_v1';
    final stored = await _store.read(key);
    if (stored != null &&
        RegExp(
          r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
        ).hasMatch(stored)) {
      return stored;
    }
    final random = Random.secure();
    final bytes = List<int>.generate(16, (_) => random.nextInt(256));
    bytes[6] = (bytes[6] & 15) | 64;
    bytes[8] = (bytes[8] & 63) | 128;
    final hex = bytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
    final id =
        '${hex.substring(0, 8)}-${hex.substring(8, 12)}-${hex.substring(12, 16)}-${hex.substring(16, 20)}-${hex.substring(20)}';
    await _store.write(key, id);
    return id;
  }

  Future<bool> _permitted({bool ask = false}) async {
    var status = await gateway.permission();
    const key = 'agapay_push_permission_requested_v1';
    if (ask &&
        status != PushPermission.allowed &&
        await _store.read(key) != 'yes') {
      // Persist before prompting: Android cannot always distinguish denied from
      // not-yet-requested. Never nag on every login or app resume.
      await _store.write(key, 'yes');
      status = await gateway.requestPermission();
    }
    return status == PushPermission.allowed;
  }

  Future<PushToken?> _wrap(String? token) async =>
      token == null || token.isEmpty
      ? null
      : PushToken(
          token: token,
          installationId: await _installationId(),
          platform: platform,
        );
  @override
  Future<PushToken?> currentToken() async {
    if (!await _permitted(ask: true)) return null;
    return _wrap(await gateway.token());
  }

  @override
  Stream<PushToken?> get changes => gateway.tokenChanges.asyncMap(
    (token) async => await _permitted() ? _wrap(token) : null,
  );
}

class FirebaseMessagingGateway implements MessagingGateway {
  FirebaseMessagingGateway(this._messaging, this.platform);
  final FirebaseMessaging _messaging;
  final PushPlatform platform;
  PushPermission _permission(NotificationSettings settings) =>
      switch (settings.authorizationStatus) {
        AuthorizationStatus.authorized ||
        AuthorizationStatus.provisional => PushPermission.allowed,
        AuthorizationStatus.denied ||
        AuthorizationStatus.deniedPermanently => PushPermission.denied,
        AuthorizationStatus.notDetermined => PushPermission.notDetermined,
      };
  @override
  Future<PushPermission> permission() async =>
      _permission(await _messaging.getNotificationSettings());
  @override
  Future<PushPermission> requestPermission() async =>
      _permission(await _messaging.requestPermission());
  @override
  Future<String?> token() async {
    if (platform == PushPlatform.ios &&
        await _messaging.getAPNSToken() == null) {
      return null;
    }
    await _messaging.setAutoInitEnabled(true);
    return _messaging.getToken();
  }

  @override
  Stream<String> get tokenChanges => _messaging.onTokenRefresh;
  @override
  Stream<Map<String, Object?>> get foreground =>
      FirebaseMessaging.onMessage.map((m) => m.data);
  @override
  Stream<Map<String, Object?>> get opened =>
      FirebaseMessaging.onMessageOpenedApp.map((m) => m.data);
  @override
  Future<Map<String, Object?>?> initialMessage() async =>
      (await _messaging.getInitialMessage())?.data;
}

@pragma('vm:entry-point')
Future<void> agapayFirebaseBackgroundMessage(RemoteMessage message) async {
  // Notification payload display is handled by the OS. Never mutate alert state
  // or access resident credentials from a background isolate.
  if (!const bool.fromEnvironment('AGAPAY_FIREBASE_ENABLED')) return;
  if (SensorPush.parse(message.data) == null) return;
  try {
    await Firebase.initializeApp();
  } catch (_) {
    /* No credential logging. */
  }
}

class FirebasePushRuntime {
  const FirebasePushRuntime({
    this.provider = const DisabledPushTokenProvider(),
    this.messages,
  });
  final PushTokenProvider provider;
  final PushMessages? messages;

  static Future<FirebasePushRuntime> initialize({
    bool enabled = const bool.fromEnvironment('AGAPAY_FIREBASE_ENABLED'),
    Future<void> Function()? initializeFirebase,
    MessagingGateway Function(PushPlatform)? gatewayFactory,
  }) async {
    if (!enabled ||
        kIsWeb ||
        (defaultTargetPlatform != TargetPlatform.android &&
            defaultTargetPlatform != TargetPlatform.iOS)) {
      return const FirebasePushRuntime();
    }
    try {
      if (initializeFirebase != null) {
        await initializeFirebase();
      } else {
        // Native configuration generated by flutterfire configure; intentionally
        // absent in Git/CI. No invented project identifiers or fallback project.
        await Firebase.initializeApp();
        FirebaseMessaging.onBackgroundMessage(agapayFirebaseBackgroundMessage);
      }
      final platform = defaultTargetPlatform == TargetPlatform.iOS
          ? PushPlatform.ios
          : PushPlatform.android;
      final gateway =
          gatewayFactory?.call(platform) ??
          FirebaseMessagingGateway(FirebaseMessaging.instance, platform);
      return FirebasePushRuntime(
        provider: FirebasePushTokenProvider(gateway, platform: platform),
        messages: gateway,
      );
    } catch (_) {
      // Push is unavailable; authenticated in-app alerts remain usable.
      return const FirebasePushRuntime();
    }
  }
}
