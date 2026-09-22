import 'dart:convert';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

abstract class SosDraftStore {
  Future<Map<String, dynamic>?> read(int userId);
  Future<void> write(int userId, Map<String, dynamic> draft);
  Future<void> clear(int userId);
}

class SecureSosDraftStore implements SosDraftStore {
  final _storage = const FlutterSecureStorage();
  String _key(int userId) => 'agapay_sos_pending_$userId';
  @override
  Future<Map<String, dynamic>?> read(int userId) async {
    final raw = await _storage.read(key: _key(userId));
    return raw == null ? null : jsonDecode(raw) as Map<String, dynamic>;
  }

  @override
  Future<void> write(int userId, Map<String, dynamic> draft) =>
      _storage.write(key: _key(userId), value: jsonEncode(draft));
  @override
  Future<void> clear(int userId) => _storage.delete(key: _key(userId));
}
