import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;
import '../models/account.dart';
import 'reader_cache.dart';

class AccountException implements Exception {
  const AccountException(this.message, {this.status, this.current});
  final String message;
  final int? status;
  final Map<String, dynamic>? current;
  @override
  String toString() => message;
}

abstract class TokenStore {
  Future<String?> read();
  Future<void> write(String token);
  Future<void> clear();
}

class SecureTokenStore implements TokenStore {
  final _storage = const FlutterSecureStorage();
  static const _key = 'agapay_session';
  @override
  Future<String?> read() => _storage.read(key: _key);
  @override
  Future<void> write(String token) => _storage.write(key: _key, value: token);
  @override
  Future<void> clear() => _storage.delete(key: _key);
}

class AuthApi {
  AuthApi({
    http.Client? client,
    TokenStore? storage,
    String? baseUrl,
    ReaderCacheStorage? readerStorage,
  }) : _client = client ?? http.Client(),
       _storage = storage ?? SecureTokenStore(),
       baseUrl = baseUrl ?? _defaultUrl {
    if (kReleaseMode) validateReleaseApiOrigin(this.baseUrl);
    reader = ReaderCache(
      server: this.baseUrl,
      storage: readerStorage ?? const SecureReaderCacheStorage(),
    );
  }

  static String get _defaultUrl {
    const configured = String.fromEnvironment('AGAPAY_API_URL');
    if (configured.isNotEmpty) return configured;
    if (!kIsWeb && defaultTargetPlatform == TargetPlatform.android) {
      return 'http://10.0.2.2:8000';
    }
    return 'http://127.0.0.1:8000';
  }

  final http.Client _client;
  final TokenStore _storage;
  final String baseUrl;
  String? _token;
  VoidCallback? onExpired;
  VoidCallback? onReaderChanged;
  late final ReaderCache reader;
  int? _readerOwner;
  int _epoch = 0;
  bool offlineReader = false;
  bool get hasSession => _token != null;
  String? cacheWarning;
  final Map<String, DateTime> _cachedReads = {};
  bool get hasCachedReads => _cachedReads.isNotEmpty;
  bool wasCached(String path) => _cachedReads.containsKey(path);
  DateTime? cachedAt(String path) => _cachedReads[path];
  bool _cacheable(String path) =>
      [
        'monitoring/stations',
        'official-notices',
        'community-alerts',
        'community-alerts/active',
        'sos',
        'response-resources',
      ].contains(path.split('?').first) ||
      RegExp(r'^community-alerts/\d+$').hasMatch(path.split('?').first);
  void _readerMode(bool value) {
    if (offlineReader != value) {
      offlineReader = value;
      onReaderChanged?.call();
    }
  }

  Future<void> _remember(
    Map<String, dynamic> profile,
    String? token,
    int epoch,
  ) async {
    if (token == null || epoch != _epoch || token != _token) return;
    _readerOwner = profile['id'] as int;
    try {
      await reader.remember(token, profile);
      if (epoch == _epoch) cacheWarning = null;
    } catch (_) {
      if (epoch == _epoch) {
        cacheWarning =
            'Encrypted offline saving is unavailable on this device.';
      }
    }
  }

  Future<void> saveReaderState(Map<String, dynamic> value) async {
    if (_readerOwner == null) return;
    try {
      await reader.patchState(_readerOwner!, value);
    } catch (_) {
      cacheWarning = 'Reader state could not be saved.';
    }
  }

  Future<Map<String, dynamic>?> restoreReaderState() async {
    if (_readerOwner == null) return null;
    try {
      return (await reader.get(_readerOwner!, 'reader-state'))?.data
          as Map<String, dynamic>?;
    } catch (_) {
      return null;
    }
  }

  Future<dynamic> request(
    String path, {
    String method = 'GET',
    Map<String, dynamic>? body,
    bool authenticated = true,
  }) async {
    if (offlineReader && authenticated && method != 'GET') {
      throw const AccountException(
        'Offline reader only. Verify the connection before sending or changing server data.',
      );
    }
    final owner = _readerOwner, epoch = _epoch, token = _token;
    try {
      final result = await _request(
        path,
        method: method,
        body: body,
        authenticated: authenticated,
        sessionToken: token,
      );
      if (epoch == _epoch && owner == _readerOwner) {
        if (_cachedReads.remove(path) != null) onReaderChanged?.call();
        if (method == 'GET' &&
            authenticated &&
            owner != null &&
            _cacheable(path)) {
          try {
            await reader.put(
              owner,
              path,
              result,
              ttl: path.startsWith('monitoring/')
                  ? const Duration(hours: 24)
                  : null,
            );
          } catch (_) {
            cacheWarning =
                'Encrypted offline saving is unavailable on this device.';
          }
        }
      }
      return result;
    } on AccountException catch (error) {
      if ((error.status == null || error.status! >= 500) &&
          method == 'GET' &&
          authenticated &&
          owner != null &&
          epoch == _epoch &&
          _cacheable(path)) {
        try {
          final cached = await reader.get(owner, path);
          if (cached != null && epoch == _epoch) {
            _cachedReads[path] = cached.savedAt;
            onReaderChanged?.call();
            return cached.data;
          }
        } catch (_) {
          cacheWarning =
              'Encrypted offline cache is unavailable or unreadable.';
        }
      }
      rethrow;
    }
  }

  Future<dynamic> _request(
    String path, {
    String method = 'GET',
    Map<String, dynamic>? body,
    bool authenticated = true,
    required String? sessionToken,
  }) async {
    final url = Uri.parse(
      '${baseUrl.replaceFirst(RegExp(r'/$'), '')}/api/$path',
    );
    if (!kDebugMode && !kIsWeb && url.scheme != 'https') {
      throw const AccountException(
        'A secure server address is required for this app build.',
      );
    }
    try {
      final requestToken = sessionToken;
      final request = http.Request(method, url)
        ..headers['Content-Type'] = 'application/json';
      if (authenticated && requestToken != null) {
        request.headers['Authorization'] = 'Bearer $requestToken';
      }
      if (body != null) request.body = jsonEncode(body);
      final response = await (() async => http.Response.fromStream(
        await _client.send(request),
      ))().timeout(const Duration(seconds: 12));
      dynamic data;
      try {
        data = response.body.isEmpty ? null : jsonDecode(response.body);
      } on FormatException {
        if (response.statusCode < 400) rethrow;
      }

      if (response.statusCode >= 400) {
        if (response.statusCode == 401 &&
            authenticated &&
            _token == requestToken) {
          try {
            await clearLocalSession();
          } catch (_) {
            cacheWarning =
                'Local secure storage could not be fully cleared; server access has ended.';
          }
          onExpired?.call();
        }
        final detail = data is Map ? data['detail'] : null;
        final message = detail is String
            ? detail
            : detail is List
            ? detail
                  .map((e) => '${(e['loc'] as List).last}: ${e['msg']}')
                  .join('\n')
            : detail is Map && detail['message'] is String
            ? detail['message'] as String
            : 'Unable to complete this request. Please try again.';
        throw AccountException(
          message,
          status: response.statusCode,
          current: detail is Map && detail['current'] is Map
              ? (detail['current'] as Map).cast<String, dynamic>()
              : null,
        );
      }
      return data;
    } on AccountException {
      rethrow;
    } on TimeoutException {
      throw const AccountException(
        'The server took too long to respond. Please try again.',
      );
    } on http.ClientException {
      throw const AccountException(
        'Unable to connect. Check your connection and try again.',
      );
    } on FormatException {
      throw const AccountException(
        'The server returned an unexpected response. Please try again.',
      );
    }
  }

  Future<Account?> restore() async {
    final epoch = _epoch;
    _token = await _storage.read();
    if (epoch != _epoch) return null;
    if (_token == null) return null;
    try {
      return await me();
    } on AccountException catch (error) {
      if (error.status == 401) return null;
      if ((error.status == null || error.status! >= 500) &&
          _token != null &&
          epoch == _epoch) {
        try {
          final profile = await reader.identity(_token!);
          if (profile != null && epoch == _epoch) {
            _readerOwner = profile['id'] as int;
            _readerMode(true);
            return Account.fromJson(profile);
          }
        } catch (_) {
          cacheWarning = 'Cached reader identity is unavailable.';
        }
      }
      rethrow;
    }
  }

  Future<Account> _requireResident(Account user) async {
    if (user.role == 'resident') return user;
    try {
      await logout();
    } catch (_) {
      await clearLocalSession();
    }
    onExpired?.call();
    throw const AccountException(
      'Staff accounts use the AGAPAY web command center.',
      status: 403,
    );
  }

  Future<Account> _accept(dynamic data) async {
    final user = Account.fromJson(data['user'] as Map<String, dynamic>);
    final token = data['access_token'] as String;
    _token = token;
    final epoch = ++_epoch;
    _readerOwner = null;
    _cachedReads.clear();
    await _requireResident(user);
    try {
      await _storage.write(token);
    } catch (_) {
      await request('auth/logout', method: 'POST').catchError((_) => null);
      _token = null;
      throw const AccountException(
        'Unable to securely save your session. Please try again.',
      );
    }
    await _remember(
      (data['user'] as Map).cast<String, dynamic>(),
      token,
      epoch,
    );
    if (epoch != _epoch) {
      throw const AccountException(
        'Account changed during sign-in. Review the current session.',
        status: 409,
      );
    }
    _readerMode(false);
    return user;
  }

  Future<Account> login(String email, String password) async => _accept(
    await request(
      'auth/login',
      method: 'POST',
      authenticated: false,
      body: {'email': email.trim(), 'password': password, 'audience': 'mobile'},
    ),
  );
  Future<Account> register(Map<String, dynamic> fields) async => _accept(
    await request(
      'auth/register',
      method: 'POST',
      authenticated: false,
      body: fields,
    ),
  );
  Future<Account> me() async {
    final token = _token, epoch = _epoch;
    final raw =
        await _request('auth/me', sessionToken: token) as Map<String, dynamic>;
    if (epoch != _epoch || token != _token) {
      throw const AccountException(
        'Account changed. Refresh manually.',
        status: 409,
      );
    }
    final user = await _requireResident(Account.fromJson(raw));
    await _remember(raw, token, epoch);
    if (epoch != _epoch || token != _token) {
      throw const AccountException("Session changed. Sign in again.");
    }
    _readerMode(false);
    return user;
  }

  Future<Account> updateProfile(Map<String, dynamic> fields) async =>
      _requireResident(
        Account.fromJson(
          await request('auth/me', method: 'PATCH', body: fields)
              as Map<String, dynamic>,
        ),
      );
  Future<void> logout({Future<void> Function()? beforeRevoke}) async {
    // Explicit logout must still revoke push registration if device DELETE
    // receives 401 and clears local API state. Keep the token only for this
    // logout request; never restore it to authenticated app state or storage.
    final logoutToken = _token;
    await beforeRevoke?.call();
    if (logoutToken != null) {
      await _request('auth/logout', method: 'POST', sessionToken: logoutToken);
    }
    await clearLocalSession();
  }

  Future<void> clearLocalSession() async {
    final owner = _readerOwner;
    ++_epoch;
    _readerOwner = null;
    _cachedReads.clear();
    _token = null;
    _readerMode(false);
    try {
      await _storage.clear();
    } finally {
      try {
        await reader.clear(owner);
      } catch (_) {
        cacheWarning = "Local encrypted cache could not be fully cleared.";
      }
    }
  }

  void dispose() => _client.close();
}

String validateReleaseApiOrigin(String origin) {
  final uri = Uri.tryParse(origin),
      host = Uri.tryParse(origin)?.host.toLowerCase() ?? '';
  if (uri == null ||
      uri.scheme != 'https' ||
      uri.userInfo.isNotEmpty ||
      uri.query.isNotEmpty ||
      uri.fragment.isNotEmpty ||
      !['', '/'].contains(uri.path) ||
      !host.contains('.') ||
      host == 'localhost' ||
      host.endsWith('.localhost') ||
      host.endsWith('.local') ||
      RegExp(r'^\d+\.').hasMatch(host)) {
    throw const AccountException(
      'A reviewed public HTTPS API origin must be injected into a release build.',
    );
  }
  return origin.replaceFirst(RegExp(r'/$'), '');
}
