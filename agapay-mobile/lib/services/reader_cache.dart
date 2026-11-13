import 'dart:convert';
import 'package:crypto/crypto.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

abstract interface class ReaderCacheStorage {
  Future<String?> read(String key);
  Future<void> write(String key, String value);
  Future<void> delete(String key);
}

/// Platform encrypted storage: Keychain/Keystore-backed secure storage.
/// Browser storage has a different device/XSS trust boundary; see rollout guide.
class SecureReaderCacheStorage implements ReaderCacheStorage {
  const SecureReaderCacheStorage();
  static const _storage = FlutterSecureStorage();
  @override
  Future<String?> read(String key) =>
      _storage.read(key: key).timeout(const Duration(seconds: 3));
  @override
  Future<void> write(String key, String value) => _storage
      .write(key: key, value: value)
      .timeout(const Duration(seconds: 3));
  @override
  Future<void> delete(String key) =>
      _storage.delete(key: key).timeout(const Duration(seconds: 3));
}

class CachedRead {
  CachedRead(this.data, this.savedAt);
  final dynamic data;
  final DateTime savedAt;
}

class ReaderCache {
  ReaderCache({
    required String server,
    required this.storage,
    DateTime Function()? now,
  }) : scope = sha256
           .convert(utf8.encode(server.replaceFirst(RegExp(r'/$'), '')))
           .toString(),
       now = now ?? DateTime.now;
  final String scope;
  final ReaderCacheStorage storage;
  final DateTime Function() now;
  Future<void>? _tail;
  static const retention = Duration(days: 7),
      maxBytes = 524288,
      maxEntryBytes = 131072,
      maxEntries = 24;
  String ownerKey(int owner) => 'agapay_reader_v1_${scope}_$owner';
  String get identityKey => 'agapay_reader_identity_v1_$scope';
  String digest(String token) => sha256.convert(utf8.encode(token)).toString();
  Future<void> _queue(Future<void> Function() action) {
    final prior = _tail;
    return _tail = prior == null
        ? action()
        : prior.catchError((_) {}).then((_) => action());
  }

  bool valid(Map value) {
    final saved = DateTime.tryParse(value['saved_at'] as String? ?? '');
    final expires = DateTime.tryParse(value['expires_at'] as String? ?? '');
    final current = now().toUtc();
    return value['format'] == 1 &&
        saved != null &&
        expires != null &&
        saved.isBefore(current.add(const Duration(minutes: 1))) &&
        current.isBefore(expires) &&
        current.difference(saved) <= retention;
  }

  Future<Map<String, dynamic>> _bundle(int owner) async {
    final raw = await storage.read(ownerKey(owner));
    if (raw == null) return {};
    if (utf8.encode(raw).length > maxBytes) {
      throw const FormatException('Reader cache exceeds its budget');
    }
    return (jsonDecode(raw) as Map).cast<String, dynamic>();
  }

  Future<void> put(int owner, String path, dynamic data, {Duration? ttl}) {
    // Copy before queueing: later widget mutations cannot alter a saved response.
    final copy = jsonDecode(jsonEncode(data));
    return _queue(() async {
      if (utf8.encode(jsonEncode(copy)).length > maxEntryBytes) {
        throw const FormatException(
          'Response exceeds the encrypted offline entry budget',
        );
      }
      final bundle = await _bundle(owner);
      bundle.removeWhere((key, value) => value is! Map || !valid(value));
      final at = now().toUtc();
      bundle[path] = {
        'format': 1,
        'saved_at': at.toIso8601String(),
        'expires_at': at.add(ttl ?? retention).toIso8601String(),
        'data': copy,
      };
      while (bundle.length > maxEntries ||
          utf8.encode(jsonEncode(bundle)).length > maxBytes) {
        final keys = bundle.keys.toList()
          ..sort(
            (a, b) => (bundle[a]['saved_at'] as String).compareTo(
              bundle[b]['saved_at'] as String,
            ),
          );
        bundle.remove(keys.first);
      }
      await storage.write(ownerKey(owner), jsonEncode(bundle));
    });
  }

  Future<CachedRead?> get(int owner, String path) async {
    CachedRead? result;
    await _queue(() async {
      final bundle = await _bundle(owner);
      final before = bundle.length;
      bundle.removeWhere((key, value) => value is! Map || !valid(value));
      if (bundle.length != before) {
        await storage.write(ownerKey(owner), jsonEncode(bundle));
      }
      final value =
          bundle[path] ??
          (path == 'monitoring/stations?history_limit=20'
              ? bundle['monitoring/stations?history_limit=120']
              : null);
      if (value is Map) {
        result = CachedRead(
          jsonDecode(jsonEncode(value['data'])),
          DateTime.parse(value['saved_at'] as String),
        );
      }
    });
    return result;
  }

  Future<void> patchState(int owner, Map<String, dynamic> values) =>
      _queue(() async {
        final bundle = await _bundle(owner), old = bundle['reader-state'];
        final data = <String, dynamic>{
          if (old is Map && valid(old) && old['data'] is Map)
            ...(old['data'] as Map).cast<String, dynamic>(),
        };
        for (final entry in values.entries) {
          if ([
                'history_offset',
                'active_offset',
                'notice_offset',
                'last_episode_id',
              ].contains(entry.key) &&
              entry.value is int &&
              entry.value >= 0 &&
              entry.value <= 2147483647) {
            data[entry.key] = entry.value;
          }
        }
        final at = now().toUtc();
        bundle['reader-state'] = {
          'format': 1,
          'saved_at': at.toIso8601String(),
          'expires_at': at.add(retention).toIso8601String(),
          'data': data,
        };
        bundle.removeWhere((key, value) => value is! Map || !valid(value));
        while (bundle.length > maxEntries ||
            utf8.encode(jsonEncode(bundle)).length > maxBytes) {
          final key = bundle.keys.firstWhere((key) => key != 'reader-state');
          bundle.remove(key);
        }
        await storage.write(ownerKey(owner), jsonEncode(bundle));
      });

  Future<void> remember(String token, Map<String, dynamic> profile) =>
      _queue(() async {
        final previous = await storage.read(identityKey);
        if (previous != null) {
          final old = jsonDecode(previous) as Map;
          if (old['owner'] is int && old['owner'] != profile['id']) {
            await storage.delete(ownerKey(old['owner'] as int));
          }
        }
        final at = now().toUtc();
        await storage.write(
          identityKey,
          jsonEncode({
            'format': 1,
            'saved_at': at.toIso8601String(),
            'expires_at': at.add(retention).toIso8601String(),
            'token_digest': digest(token),
            'owner': profile['id'],
            'profile': profile,
          }),
        );
      });
  Future<Map<String, dynamic>?> identity(String token) async {
    Map<String, dynamic>? result;
    await _queue(() async {
      final raw = await storage.read(identityKey);
      if (raw == null) return;
      if (utf8.encode(raw).length > 16384) {
        await storage.delete(identityKey);
        return;
      }
      final row = jsonDecode(raw) as Map;
      if (!valid(row)) {
        await storage.delete(identityKey);
        if (row['owner'] is int) {
          await storage.delete(ownerKey(row['owner'] as int));
        }
        return;
      }
      if (row['token_digest'] != digest(token)) return;
      final profile = (row['profile'] as Map).cast<String, dynamic>();
      if (profile['role'] == 'resident' && profile['id'] == row['owner']) {
        result = profile;
      }
    });
    return result;
  }

  Future<void> clear(int? owner) => _queue(() async {
    await storage.delete(identityKey);
    if (owner != null) await storage.delete(ownerKey(owner));
  });
}
