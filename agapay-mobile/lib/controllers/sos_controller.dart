import 'dart:math';
import 'package:flutter/foundation.dart';
import '../models/sos_request.dart';
import '../services/auth_api.dart';
import '../services/sos_drafts.dart';

class SosController extends ChangeNotifier {
  SosController(this.api, {SosDraftStore? storage})
    : storage = storage ?? SecureSosDraftStore();
  final AuthApi api;
  final SosDraftStore storage;
  int? _owner;
  int _generation = 0;
  int _readRevision = 0;
  bool _disposed = false;
  bool ready = false, sending = false, loading = false;
  String? error;
  DateTime? syncedAt;
  Map<String, dynamic>? pending;
  List<SosRequest> items = [];
  int total = 0, _limit = 50;
  SosRequest? lastSent;
  void _notify() {
    if (!_disposed) notifyListeners();
  }

  Future<void> setOwner(int? owner) async {
    if (_owner == owner) return;
    final generation = ++_generation;
    _owner = owner;
    ready = false;
    sending = false;
    loading = false;
    items = [];
    total = 0;
    _limit = 50;
    lastSent = null;
    pending = null;
    syncedAt = null;
    error = null;
    _notify();
    if (owner == null) return;
    try {
      final draft = await storage.read(owner);
      if (generation != _generation || _disposed) return;
      pending = draft;
      ready = true;
      _notify();
      await refresh();
    } catch (_) {
      if (generation != _generation || _disposed) return;
      error =
          'Unable to read your saved request reference. Reopen the app before sending to avoid a duplicate request.';
      _notify();
    }
  }

  Future<void> refresh({bool more = false}) async {
    if (_owner == null || loading || sending || !ready) return;
    final generation = _generation;
    final revision = ++_readRevision;
    loading = true;
    if (more) _limit += 50;
    _notify();
    try {
      final next = <SosRequest>[];
      var count = 0;
      for (var offset = 0; offset < _limit; offset += 50) {
        final data =
            await api.request('sos?limit=50&offset=$offset')
                as Map<String, dynamic>;
        if (generation != _generation ||
            revision != _readRevision ||
            _disposed) {
          return;
        }
        count = data['total'] as int;
        next.addAll(
          (data['items'] as List).map(
            (e) => SosRequest.fromJson(e as Map<String, dynamic>),
          ),
        );
        if (offset + 50 >= count) break;
      }
      // A submission may have started while this GET was in flight.
      if (sending) return;
      items = {for (final item in next) item.id: item}.values.toList();
      total = count;
      if (lastSent != null) {
        for (final item in items) {
          if (item.id == lastSent!.id) lastSent = item;
        }
      }
      if (pending != null) {
        for (final item in items) {
          if (item.requestId == pending!['request_id']) {
            lastSent = item;
            await storage.clear(_owner!);
            if (generation != _generation || _disposed) return;
            pending = null;
            break;
          }
        }
      }
      error = null;
      syncedAt = DateTime.now();
    } catch (e) {
      if (generation == _generation && !_disposed) {
        error =
            'Status refresh failed. Displayed information may be out of date. ${e is AccountException ? e.message : "Please retry."}';
      }
    } finally {
      if (generation == _generation && !_disposed) {
        loading = false;
        _notify();
      }
    }
  }

  static String _reference() {
    final random = Random.secure();
    final b = List.generate(16, (_) => random.nextInt(256));
    b[6] = (b[6] & 15) | 64;
    b[8] = (b[8] & 63) | 128;
    final h = b.map((v) => v.toRadixString(16).padLeft(2, '0')).join();
    return '${h.substring(0, 8)}-${h.substring(8, 12)}-${h.substring(12, 16)}-${h.substring(16, 20)}-${h.substring(20)}';
  }

  Future<SosRequest?> send(Map<String, dynamic> fields) async {
    if (_owner == null || !ready || sending) return null;
    final owner = _owner!, generation = _generation;
    ++_readRevision;
    sending = true;
    error = null;
    pending ??= {...fields, 'request_id': _reference()};
    final payload = Map<String, dynamic>.from(pending!);
    _notify();
    var transmitted = false;
    try {
      // Save before POST so a timeout or app restart can retry the exact same reference.
      await storage.write(owner, payload);
      if (generation != _generation || _disposed) return null;
      transmitted = true;
      final data =
          await api.request('sos', method: 'POST', body: payload)
              as Map<String, dynamic>;
      if (generation != _generation || _disposed) return null;
      final item = SosRequest.fromJson(data);
      lastSent = item;
      items = [item, ...items.where((v) => v.id != item.id)];
      pending = null;
      try {
        await storage.clear(owner);
      } catch (_) {
        /* Retry will return the same saved request. */
      }
      return item;
    } catch (e) {
      if (generation != _generation || _disposed) return null;
      final rejected =
          e is AccountException && [400, 403, 422].contains(e.status);
      if (rejected) {
        try {
          await storage.clear(owner);
          pending = null;
        } catch (_) {
          /* Keep its reference until storage is available. */
        }
      }
      error = !transmitted
          ? 'Nothing was sent: unable to save the request reference. Retry when device storage is available.'
          : rejected
          ? 'Request was not accepted. ${e.message}'
          : 'Receipt is unconfirmed. Check history or retry this same request; do not create a duplicate. ${e is AccountException ? e.message : "Connection failed."}';
      return null;
    } finally {
      if (generation == _generation && !_disposed) {
        sending = false;
        _notify();
      }
    }
  }

  Future<SosRequest?> updateLocation(
    int sosId, {
    required double latitude,
    required double longitude,
    required double accuracyM,
    required DateTime recordedAt,
  }) async {
    if (_owner == null || _disposed) return null;
    final generation = _generation;
    try {
      final data =
          await api.request(
                'sos/$sosId/location',
                method: 'PATCH',
                body: {
                  'latitude': latitude,
                  'longitude': longitude,
                  'accuracy_m': accuracyM,
                  'location_recorded_at': recordedAt.toUtc().toIso8601String(),
                },
              )
              as Map<String, dynamic>;
      if (generation != _generation || _disposed) return null;
      final updated = SosRequest.fromJson(data);
      items = [updated, ...items.where((item) => item.id != updated.id)];
      if (lastSent?.id == updated.id) lastSent = updated;
      error = null;
      syncedAt = DateTime.now();
      _notify();
      return updated;
      } on AccountException catch (e) {
        if (generation != _generation || _disposed) return null;
        // A resolved request and an out-of-order fix are normal stream stop/race cases.
      if (e.status != 409) {
        error = 'Live location update failed. ${e.message}';
        _notify();
      }
      return null;
    } catch (_) {
      if (generation == _generation && !_disposed) {
        error = 'Live location is waiting for a connection.';
        _notify();
      }
      return null;
    }
  }

  @override
  void dispose() {
    _disposed = true;
    ++_generation;
    super.dispose();
  }
}
