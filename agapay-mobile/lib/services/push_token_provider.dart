/// Provider boundary only. Firebase initialization, permission prompts and
/// delivery listeners belong to a future adapter, not this foundation.
enum PushPlatform { android, ios }

class PushToken {
  const PushToken({
    required String token,
    required this.installationId,
    required this.platform,
  }) : _token = token;

  final String _token;

  /// Stable UUID persisted by the future provider per app installation.
  final String installationId;
  final PushPlatform platform;

  Map<String, Object> get registrationBody => {
    'provider': 'fcm',
    'platform': platform.name,
    'installation_id': installationId,
    'provider_token': _token,
  };

  bool sameRegistration(PushToken other) =>
      _token == other._token &&
      installationId == other.installationId &&
      platform == other.platform;

  @override
  String toString() => 'PushToken(redacted)';
}

abstract class PushTokenProvider {
  bool get supported;
  Future<PushToken?> currentToken();

  /// null means token/permission withdrawn; deregister the current device.
  Stream<PushToken?> get changes;
}

class DisabledPushTokenProvider implements PushTokenProvider {
  const DisabledPushTokenProvider();
  @override
  bool get supported => false;
  @override
  Future<PushToken?> currentToken() async => null;
  @override
  Stream<PushToken?> get changes => const Stream.empty();
}
