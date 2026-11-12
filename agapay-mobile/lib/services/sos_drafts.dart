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
    if (raw != null && utf8.encode(raw).length > 16384) {
      throw const FormatException('Saved SOS exceeds its size budget');
    }
    return raw == null ? null : jsonDecode(raw) as Map<String, dynamic>;
  }

  @override
  Future<void> write(int userId, Map<String, dynamic> draft) {
    final raw = jsonEncode(draft);
    if (utf8.encode(raw).length > 16384) {
      throw const FormatException('Saved SOS exceeds its size budget');
    }
    return _storage.write(key: _key(userId), value: raw);
  }

  @override
  Future<void> clear(int userId) => _storage.delete(key: _key(userId));
}
