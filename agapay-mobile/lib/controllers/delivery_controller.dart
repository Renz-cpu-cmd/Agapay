import 'dart:async';
import 'package:flutter/foundation.dart';
import '../services/auth_api.dart';
import '../services/notification_receipts.dart';

class DeliveryController extends ChangeNotifier {
  DeliveryController(this.api, {ReceiptStorage? storage})
    : receipts = NotificationReceiptJournal(api, storage: storage);
  final AuthApi api;
  final NotificationReceiptJournal receipts;
  int? _owner, nextBefore;
  int _generation = 0;
  bool _disposed = false, _foreground = true;
  bool loading = false, saving = false, conflicted = false;
  String? error;
  Map<String, dynamic>? consent;
  List<Map<String, dynamic>> items = const [];
  void _notify() {
    if (!_disposed) notifyListeners();
  }

  void setOwner(int? owner) {
    if (_owner == owner) return;
    _owner = owner;
    ++_generation;
    items = const [];
    consent = null;
    nextBefore = null;
    loading = false;
    saving = false;
    conflicted = false;
    error = null;
    _notify();
  }

  void setForeground(bool value) {
    if (_foreground == value) return;
    _foreground = value;
    ++_generation;
    loading = false;
    saving = false;
    if (value && _owner != null) {
      unawaited(receipts.flush());
      if (consent != null) unawaited(refresh());
    }
  }

  Future<void> capture(Map<String, Object?> data, String stage) async {
    final saved = await receipts.capture(data, stage);
    if (saved) await receipts.flush(limit: 2);
    _notify();
  }

  Future<void> refresh({int? before}) async {
    if (_owner == null || !_foreground || loading || _disposed) return;
    final generation = _generation;
    loading = true;
    _notify();
    try {
      final result = await api.request(
        'notification-deliveries?limit=20${before == null ? '' : '&before_id=$before'}',
      );
      final preferences = await api.request('notification-deliveries/consent');
      if (_disposed || generation != _generation) return;
      if (result is! Map ||
          result['items'] is! List ||
          preferences is! Map ||
          preferences['version'] is! int) {
        throw const FormatException('Delivery evidence response unavailable');
      }
      items = List.unmodifiable(
        (result['items'] as List).map(
          (item) => Map<String, dynamic>.unmodifiable(
            (item as Map).cast<String, dynamic>(),
          ),
        ),
      );
      nextBefore = result['next_before_id'] as int?;
      consent = Map.unmodifiable(preferences.cast<String, dynamic>());
      error = null;
      conflicted = false;
      await receipts.flush();
    } catch (reason) {
      if (generation == _generation && !_disposed) {
        error = reason is AccountException
            ? reason.message
            : 'Delivery evidence is unavailable; received stages are unknown.';
      }
    } finally {
      if (generation == _generation && !_disposed) {
        loading = false;
        _notify();
      }
    }
  }

  Future<void> changeConsent(bool enabled) async {
    if (consent == null ||
        saving ||
        conflicted ||
        _owner == null ||
        !_foreground) {
      return;
    }
    final generation = _generation;
    saving = true;
    _notify();
    try {
      final result = await api.request(
        'notification-deliveries/consent',
        method: 'POST',
        body: {'enabled': enabled, 'expected_version': consent!['version']},
      );
      if (generation == _generation && !_disposed) {
        consent = Map.unmodifiable((result as Map).cast<String, dynamic>());
        error = null;
      }
    } catch (reason) {
      if (generation == _generation && !_disposed) {
        conflicted = reason is AccountException && reason.status == 409;
        error = reason is AccountException
            ? reason.message
            : 'Receipt preference could not be saved.';
      }
    } finally {
      if (generation == _generation && !_disposed) {
        saving = false;
        _notify();
      }
    }
  }

  Future<void> acknowledge(int id, int version) async {
    if (saving || conflicted || _owner == null || !_foreground) return;
    final generation = _generation;
    saving = true;
    _notify();
    try {
      final result = await api.request(
        'notification-deliveries/$id/acknowledge',
        method: 'POST',
        body: {'expected_version': version, 'confirmed': true},
      );
      if (generation == _generation && !_disposed) {
        items = List.unmodifiable(
          items.map(
            (item) => item['id'] == id
                ? Map<String, dynamic>.unmodifiable(
                    (result as Map).cast<String, dynamic>(),
                  )
                : item,
          ),
        );
        error = null;
      }
    } catch (reason) {
      if (generation == _generation && !_disposed) {
        conflicted = reason is AccountException && reason.status == 409;
        error = reason is AccountException
            ? reason.message
            : 'Acknowledgement is unconfirmed. Refresh before another action.';
      }
    } finally {
      if (generation == _generation && !_disposed) {
        saving = false;
        _notify();
      }
    }
  }

  @override
  void dispose() {
    _disposed = true;
    ++_generation;
    super.dispose();
  }
}
