import 'dart:convert';
import 'package:crypto/crypto.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'auth_api.dart';
import 'push_messaging.dart';

abstract interface class ReceiptStorage {
  Future<Map<String, String>> readAll();
  Future<void> write(String key, String value);
  Future<void> delete(String key);
}

/// Dedicated namespace: background callbacks never read resident API credentials.
class SecureReceiptStorage implements ReceiptStorage {
  const SecureReceiptStorage();
  static const _storage = FlutterSecureStorage(
    aOptions: AndroidOptions(
      storageNamespace: 'agapay_notification_receipts_v1',
    ),
    iOptions: IOSOptions(accountName: 'agapay_notification_receipts_v1'),
  );
  @override
  Future<Map<String, String>> readAll() =>
      _storage.readAll().timeout(const Duration(seconds: 3));
  @override
  Future<void> write(String key, String value) => _storage
      .write(key: key, value: value)
      .timeout(const Duration(seconds: 3));
  @override
  Future<void> delete(String key) =>
      _storage.delete(key: key).timeout(const Duration(seconds: 3));
}

class NotificationReceiptJournal {
  NotificationReceiptJournal(
    this.api, {
    ReceiptStorage? storage,
    DateTime Function()? now,
  }) : storage = storage ?? const SecureReceiptStorage(),
       now = now ?? DateTime.now;
  final AuthApi api;
  final ReceiptStorage storage;
  final DateTime Function() now;
  bool _flushing = false;
  int pending = 0;
  String? warning;
  String get _prefix => 'receipt_${sha256.convert(utf8.encode(api.baseUrl))}_';

  Future<bool> capture(Map<String, Object?> data, String stage) async {
    if (SensorPush.parse(data) == null ||
        !['RECEIVED', 'OPENED'].contains(stage)) {
      return false;
    }
    final id = data['delivery_id'],
        attempt = data['attempt_no'],
        token = data['receipt_token'];
    if (id is! String ||
        !RegExp(r'^[1-9][0-9]{0,14}$').hasMatch(id) ||
        attempt is! String ||
        !RegExp(r'^[1-9][0-9]?$|^100$').hasMatch(attempt) ||
        token is! String ||
        !RegExp(r'^[A-Za-z0-9_-]{40,80}$').hasMatch(token)) {
      return false;
    }
    try {
      final values = await _entries();
      final key = '$_prefix${id}_${attempt}_$stage';
      if (values.containsKey(key)) return true;
      if (values.length >= 200) {
        warning = 'Receipt buffer full; this callback could not be saved.';
        return false;
      }
      // Independent keys prevent another isolate from overwriting a shared index.
      await storage.write(
        key,
        jsonEncode({
          'delivery_id': int.parse(id),
          'attempt_no': int.parse(attempt),
          'stage': stage,
          'receipt_token': token,
          'reported_at': now().toUtc().toIso8601String(),
        }),
      );
      pending = values.length + 1;
      warning = null;
      return true;
    } catch (_) {
      warning = 'Encrypted receipt saving is unavailable.';
      return false;
    }
  }

  Future<Map<String, String>> _entries() async {
    final all = await storage.readAll(), values = <String, String>{};
    for (final entry in all.entries.where(
      (entry) => entry.key.startsWith(_prefix),
    )) {
      try {
        final value = jsonDecode(entry.value) as Map;
        final captured = DateTime.parse(value['reported_at'] as String);
        if (now().toUtc().difference(captured.toUtc()) >
            const Duration(days: 7)) {
          await storage.delete(entry.key);
          warning =
              'Some unconfirmed callbacks expired from the local receipt queue; they were not recorded.';
          continue;
        }
        values[entry.key] = entry.value;
      } catch (_) {
        await storage.delete(entry.key);
      }
    }
    pending = values.length;
    return values;
  }

  Future<void> refreshPending() async {
    try {
      await _entries();
    } catch (_) {
      warning = 'Receipt queue is unavailable.';
    }
  }

  Future<void> flush({int limit = 10}) async {
    if (_flushing) return;
    _flushing = true;
    try {
      final entries = await _entries();
      for (final entry in entries.entries.take(limit)) {
        try {
          await api
              .request(
                'notification-receipts',
                method: 'POST',
                authenticated: false,
                body: (jsonDecode(entry.value) as Map).cast<String, dynamic>(),
              )
              .timeout(const Duration(seconds: 5));
          await storage.delete(entry.key);
          pending--;
        } on AccountException catch (error) {
          if ([400, 403, 404, 410, 422].contains(error.status)) {
            await storage.delete(entry.key);
            pending--;
            warning =
                'Some receipt capabilities expired or were withdrawn; those callbacks were not recorded.';
          } else {
            warning =
                'Receipt callbacks remain queued; server receipt is unconfirmed.';
            break;
          }
        } catch (_) {
          warning =
              'Receipt callbacks remain queued; server receipt is unconfirmed.';
          break;
        }
      }
    } catch (_) {
      warning = 'Receipt queue could not be inspected.';
    } finally {
      _flushing = false;
    }
  }
}
