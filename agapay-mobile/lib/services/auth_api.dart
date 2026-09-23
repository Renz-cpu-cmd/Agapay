import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;
import '../models/account.dart';

class AccountException implements Exception {
  const AccountException(this.message, {this.status});
  final String message;
  final int? status;
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
  AuthApi({http.Client? client, TokenStore? storage, String? baseUrl})
    : _client = client ?? http.Client(),
      _storage = storage ?? SecureTokenStore(),
      baseUrl = baseUrl ?? _defaultUrl;

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

  Future<dynamic> request(
    String path, {
    String method = 'GET',
    Map<String, dynamic>? body,
    bool authenticated = true,
  }) => _request(
    path,
    method: method,
    body: body,
    authenticated: authenticated,
    sessionToken: _token,
  );

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
      final data = response.body.isEmpty ? null : jsonDecode(response.body);
      if (response.statusCode >= 400) {
        if (response.statusCode == 401 &&
            authenticated &&
            _token == requestToken) {
          await clearLocalSession();
          onExpired?.call();
        }
        final detail = data is Map ? data['detail'] : null;
        final message = detail is String
            ? detail
            : detail is List
            ? detail
                  .map((e) => '${(e['loc'] as List).last}: ${e['msg']}')
                  .join('\n')
            : 'Unable to complete this request. Please try again.';
        throw AccountException(message, status: response.statusCode);
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
    _token = await _storage.read();
    if (_token == null) return null;
    try {
      return await me();
    } on AccountException catch (error) {
      if (error.status == 401) return null;
      rethrow;
    }
  }

  Future<Account> _accept(dynamic data) async {
    final user = Account.fromJson(data['user'] as Map<String, dynamic>);
    final token = data['access_token'] as String;
    _token = token;
    if (user.role != 'resident') {
      await logout();
      throw const AccountException(
        'Staff accounts use the AGAPAY web command center.',
      );
    }
    try {
      await _storage.write(token);
    } catch (_) {
      await request('auth/logout', method: 'POST').catchError((_) => null);
      _token = null;
      throw const AccountException(
        'Unable to securely save your session. Please try again.',
      );
    }
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
  Future<Account> me() async =>
      Account.fromJson(await request('auth/me') as Map<String, dynamic>);
  Future<Account> updateProfile(Map<String, dynamic> fields) async =>
      Account.fromJson(
        await request('auth/me', method: 'PATCH', body: fields)
            as Map<String, dynamic>,
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
    _token = null;
    await _storage.clear();
  }

  void dispose() => _client.close();
}
