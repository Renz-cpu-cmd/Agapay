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
  bool ready = false, sending = false, loading = false, clearing = false;
  String? error;
  DateTime? syncedAt;
  Map<String, dynamic>? pending;
  String pendingState = 'none';
  DateTime? queuedAt, lastAttemptAt;
  bool fromCache = false;
  Map<String, dynamic>? _lastReceipt;
  List<SosRequest> items = [];
  int total = 0, _limit = 50;
  SosRequest? lastSent;
  final locationConflicts = <int>{};
  void _notify() {
    if (!_disposed) notifyListeners();
  }

  Future<void> setOwner(int? owner) async {
    if (_owner == owner) return;
    final generation = ++_generation;
    _owner = owner;
    ready = false;
    sending = false;
    clearing = false;
    loading = false;
    items = [];
    total = 0;
    _limit = 50;
    lastSent = null;
    pending = null;
    pendingState = 'none';
    queuedAt = null;
    lastAttemptAt = null;
    fromCache = false;
    _lastReceipt = null;
    locationConflicts.clear();
    syncedAt = null;
    error = null;
    _notify();
    if (owner == null) return;
    try {
      final draft = await storage.read(owner);
      if (generation != _generation || _disposed) return;
      if (draft != null) {
        final meta = draft['_outbox'] as Map?;
        pending = Map<String, dynamic>.from(draft)..remove('_outbox');
        pendingState = meta?['server'] != null && meta!['server'] != api.baseUrl
            ? 'conflict'
            : meta?['state'] as String? ?? 'unknown';
        queuedAt = DateTime.tryParse(meta?['queued_at'] as String? ?? '');
        lastAttemptAt = DateTime.tryParse(
          meta?['last_attempt_at'] as String? ?? '',
        );
        if (pendingState != 'conflict' && meta?['last_receipt'] is Map) {
          _lastReceipt = (meta!['last_receipt'] as Map).cast<String, dynamic>();
          lastSent = SosRequest.fromJson(_lastReceipt!);
        }
        if (pendingState == 'received') pending = null;
      }
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

  Future<void> refresh({bool more = false, bool manual = false}) async {
    if (_owner == null || loading || sending || clearing || !ready) return;
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
      if (manual) {
        locationConflicts.removeWhere(
          (id) => items.any((item) => item.id == id),
        );
      }
      total = count;
      if (lastSent != null) {
        for (final item in items) {
          if (item.id == lastSent!.id) lastSent = item;
        }
      }
      fromCache = api.wasCached('sos?limit=50&offset=0');
      if (pending != null && !api.offlineReader && pendingState == 'unknown') {
        final lookupPayload = Map<String, dynamic>.from(pending!);
        final receipt =
            await api.request(
                  'sos/receipt',
                  method: 'POST',
                  body: lookupPayload,
                )
                as Map;
        if (generation != _generation ||
            revision != _readRevision ||
            _disposed ||
            sending) {
          return;
        }
        if (receipt['receipt'] == 'received') {
          final received = SosRequest.fromJson(
            (receipt['item'] as Map).cast<String, dynamic>(),
          );
          if (received.requestId != lookupPayload['request_id']) {
            throw const FormatException('Receipt reference mismatch');
          }
          _lastReceipt = (receipt['item'] as Map).cast<String, dynamic>();
          lastSent = received;
          items = [lastSent!, ...items.where((i) => i.id != lastSent!.id)];
          await _save(_owner!, 'received');
          if (generation != _generation || _disposed) return;
          pending = null;
          pendingState = 'received';
        } else if (receipt['receipt'] == 'conflict') {
          await _save(_owner!, 'conflict');
        }
      }
      error = fromCache
          ? 'OFFLINE · Last-known received history. Current response status is unconfirmed.'
          : null;
      syncedAt = fromCache
          ? api.cachedAt('sos?limit=50&offset=0')
          : DateTime.now();
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
    if (_owner == null ||
        !ready ||
        sending ||
        clearing ||
        pendingState == 'conflict' ||
        pendingState == 'rejected') {
      return null;
    }
    final owner = _owner!, generation = _generation;
    ++_readRevision;
    sending = true;
    error = null;
    if (pending == null) {
      pending = {...fields, 'request_id': _reference()};
      queuedAt = DateTime.now().toUtc();
      lastAttemptAt = null;
    }
    final payload = Map<String, dynamic>.from(pending!);
    _notify();
    final earlierAttemptUnconfirmed = pendingState == 'unknown';
    var transmitted = false;
    try {
      // Save before POST so a timeout or app restart can retry the exact same reference.
      await _save(owner, pendingState == 'unknown' ? 'unknown' : 'queued');
      if (generation != _generation || _disposed) return null;
      if (api.offlineReader) {
        error = pendingState == 'unknown'
            ? 'Receipt remains unconfirmed. The exact reference is saved; verify the connection before checking receipt or retrying.'
            : 'Queued on this device. NOT RECEIVED by the server. Verify the connection, then choose to send this exact request.';
        return null;
      }
      lastAttemptAt = DateTime.now().toUtc();
      await _save(owner, 'unknown');
      if (generation != _generation || _disposed) return null;
      transmitted = true;
      final data =
          await api.request('sos', method: 'POST', body: payload)
              as Map<String, dynamic>;
      if (generation != _generation || _disposed) return null;
      final item = SosRequest.fromJson(data);
      if (item.requestId != payload['request_id']) {
        throw const FormatException('Receipt reference mismatch');
      }
      _lastReceipt = Map<String, dynamic>.from(data);
      lastSent = item;
      items = [item, ...items.where((v) => v.id != item.id)];
      await _save(owner, 'received');
      if (generation != _generation || _disposed) return null;
      pending = null;
      pendingState = 'received';
      return item;
    } catch (e) {
      if (generation != _generation || _disposed) return null;
      final rejected =
          e is AccountException && [400, 403, 422].contains(e.status);
      if (rejected && !earlierAttemptUnconfirmed) {
        try {
          pendingState = 'rejected';
          await _save(owner, 'rejected', message: e.message);
        } catch (_) {
          /* Keep its reference until storage is available. */
        }
      }
      if (e is AccountException && e.status == 409) {
        try {
          pendingState = 'conflict';
          await _save(owner, 'conflict', message: e.message);
        } catch (_) {}
      }
      error = !transmitted
          ? 'Nothing was sent: unable to save the request reference. Retry when device storage is available.'
          : rejected && !earlierAttemptUnconfirmed
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

  Future<void> _save(int owner, String state, {String? message}) async {
    if (pending == null) return;
    final generation = _generation, reference = pending!['request_id'];
    await storage.write(owner, {
      ...pending!,
      '_outbox': {
        'format': 2,
        'server': api.baseUrl,
        'state': state,
        'queued_at': queuedAt?.toIso8601String(),
        'last_attempt_at': lastAttemptAt?.toIso8601String(),
        if (_lastReceipt != null) 'last_receipt': _lastReceipt,
        if (message != null)
          'last_error': message.substring(
            0,
            message.length > 300 ? 300 : message.length,
          ),
      },
    });
    if (generation == _generation && pending?['request_id'] == reference) {
      pendingState = state;
    }
  }

  Future<void> discardUnsent() async {
    if (_owner == null ||
        sending ||
        clearing ||
        loading ||
        !['queued', 'rejected'].contains(pendingState)) {
      return;
    }
    final generation = _generation, owner = _owner!;
    clearing = true;
    _notify();
    try {
      if (_lastReceipt == null) {
        await storage.clear(owner);
      } else {
        await storage.write(owner, {
          '_outbox': {
            'format': 2,
            'server': api.baseUrl,
            'state': 'received',
            'last_receipt': _lastReceipt,
          },
        });
      }
      if (generation != _generation || _disposed) return;
      pending = null;
      pendingState = 'none';
      queuedAt = null;
      lastAttemptAt = null;
      error = null;
    } finally {
      if (generation == _generation && !_disposed) {
        clearing = false;
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
    if (_owner == null || _disposed || locationConflicts.contains(sosId)) {
      return null;
    }
    final known =
        items.where((item) => item.id == sosId).firstOrNull ??
        (lastSent?.id == sosId ? lastSent : null);
    if (known == null) {
      error = 'Refresh and review this request before sharing location.';
      _notify();
      return null;
    }
    ++_readRevision;
    final generation = _generation;
    try {
      final data =
          await api.request(
                'sos/$sosId/location',
                method: 'PATCH',
                body: {
                  'expected_version': known.version,
                  'latitude': latitude,
                  'longitude': longitude,
                  'accuracy_m': accuracyM,
                  'location_recorded_at': recordedAt.toUtc().toIso8601String(),
                },
              )
              as Map<String, dynamic>;
      if (generation != _generation || _disposed) return null;
      final updated = SosRequest.fromJson(data);
      ++_readRevision;
      items = [updated, ...items.where((item) => item.id != updated.id)];
      if (lastSent?.id == updated.id) lastSent = updated;
      error = null;
      syncedAt = DateTime.now();
      _notify();
      return updated;
    } on AccountException catch (e) {
      if (generation != _generation || _disposed) return null;
      if (e.status == 409) {
        locationConflicts.add(sosId);
        error =
            'Location sharing paused. Refresh and review the request, then explicitly resume sharing. ${e.message}';
        _notify();
      } else {
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
