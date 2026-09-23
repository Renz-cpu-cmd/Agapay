import 'dart:async';
import 'package:flutter/foundation.dart';
import '../services/auth_api.dart';
import '../services/push_token_provider.dart';

enum NotificationRegistrationState {
  disabled,
  waiting,
  registering,
  registered,
  unavailable,
}

/// Uses AuthApi exclusively. No token in UI state, errors, or logs.
class NotificationRegistrationController extends ChangeNotifier {
  NotificationRegistrationController(
    this._api, {
    PushTokenProvider provider = const DisabledPushTokenProvider(),
  }) : _provider = provider;

  final AuthApi _api;
  final PushTokenProvider _provider;
  StreamSubscription<PushToken?>? _subscription;
  Future<void> _tail = Future.value();
  int? _owner;
  int _generation = 0;
  bool _disposed = false;
  bool _stopping = false;
  String? _deviceId;
  PushToken? _registeredToken;
  NotificationRegistrationState state = NotificationRegistrationState.disabled;

  /// Allows tests/callers to await all currently queued registration work.
  Future<void> get settled => _tail;

  void setOwner(int? owner) {
    if (_disposed || owner == _owner) return;
    _generation++;
    _owner = owner;
    _stopping = false;
    unawaited(_subscription?.cancel());
    _subscription = null;
    _deviceId = null;
    _registeredToken = null;
    _setState(
      _provider.supported && owner != null
          ? NotificationRegistrationState.waiting
          : NotificationRegistrationState.disabled,
    );
    if (owner == null || !_provider.supported) return;
    // Queue the initial read before stream events so a slow read cannot overwrite
    // a newer rotation. Every request is serialized and owner-generation checked.
    unawaited(refresh());
    _subscription = _provider.changes.listen(
      (token) => _queue(() async => token),
      onError: (Object _) {
        if (!_disposed && _owner != null) {
          _setState(NotificationRegistrationState.unavailable);
        }
      },
    );
  }

  Future<void> refresh() => _queue(_provider.currentToken);

  Future<void> _queue(Future<PushToken?> Function() read) {
    if (_disposed || _stopping || _owner == null || !_provider.supported) {
      return Future.value();
    }
    final version = _generation;
    _tail = _tail.then((_) async {
      if (!_current(version) || _stopping) return;
      try {
        final token = await read().timeout(const Duration(seconds: 12));
        if (!_current(version) || _stopping) return;
        if (token == null) {
          await _remove();
          if (_current(version)) {
            _setState(NotificationRegistrationState.waiting);
          }
          return;
        }
        if (_registeredToken?.sameRegistration(token) == true) return;
        _setState(NotificationRegistrationState.registering);
        final response = await _api.request(
          'notification-devices',
          method: 'POST',
          body: token.registrationBody,
        );
        if (!_current(version)) return;
        if (response is! Map<String, dynamic> ||
            response['id'] is! String ||
            (response['id'] as String).isEmpty ||
            response['enabled'] != true) {
          throw const FormatException('Invalid device registration');
        }
        _deviceId = response['id'] as String;
        _registeredToken = token;
        _setState(NotificationRegistrationState.registered);
      } catch (_) {
        // AuthApi handles 401/expiry centrally. Do not expose provider/server
        // errors that could contain the registration token.
        if (_current(version)) {
          _setState(NotificationRegistrationState.unavailable);
        }
      }
    });
    return _tail;
  }

  bool _current(int version) =>
      !_disposed && _owner != null && version == _generation;

  Future<void> _remove() async {
    final id = _deviceId;
    if (id != null) {
      try {
        await _api.request(
          'notification-devices/${Uri.encodeComponent(id)}',
          method: 'DELETE',
        );
      } on AccountException catch (error) {
        if (error.status != 404) rethrow;
      }
    }
    _deviceId = null;
    _registeredToken = null;
  }

  /// Drain an in-flight registration before logout revokes its session.
  /// Failed deletion does not prevent logout; backend session eligibility is
  /// the fallback. A provider send already in flight cannot be recalled.
  Future<void> unregisterForLogout() async {
    _stopping = true;
    await _subscription?.cancel();
    _subscription = null;
    await _tail;
    try {
      await _remove();
    } catch (_) {
      // Never log request bodies/provider tokens.
    }
    setOwner(null);
  }

  void _setState(NotificationRegistrationState value) {
    if (_disposed) return;
    state = value;
    notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    _generation++;
    unawaited(_subscription?.cancel());
    _deviceId = null;
    _registeredToken = null;
    super.dispose();
  }
}
