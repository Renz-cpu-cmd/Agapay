import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:geolocator/geolocator.dart';

import '../services/auth_api.dart';

/// Migration 0010: an administrator-granted session lets this phone report GPS fixes for
/// one portable station. Fixes go only to the station-tracking API; they never change the
/// station's registry coordinates, commissioning or warning eligibility.
class TrackingSession {
  TrackingSession.fromJson(Map<String, dynamic> json)
    : id = json['id'] as String,
      stationId = json['station_id'] as String,
      stationName = (json['station_name'] as String?) ?? json['station_id'] as String,
      expiresAt = _utcInstant(json['expires_at'] as String?);
  final String id, stationId, stationName;
  final DateTime? expiresAt;
}

/// Server times are UTC. A value without an offset is read as UTC, never device local time
/// (otherwise a phone at UTC+8 would treat a fresh session as expired).
DateTime? _utcInstant(String? value) {
  if (value == null || value.isEmpty) return null;
  final hasOffset = RegExp(r'(Z|[+-]\d{2}:?\d{2})$').hasMatch(value);
  return DateTime.tryParse(hasOffset ? value : '${value}Z')?.toUtc();
}

class TrackingFix {
  const TrackingFix(this.latitude, this.longitude, this.accuracyM, this.capturedAt);
  final double latitude, longitude, accuracyM;
  final DateTime capturedAt;
}

/// Source of one GPS fix. Production uses Geolocator; tests inject fixes.
abstract class StationPositionSource {
  Future<String?> ensurePermission();
  Future<TrackingFix> current();
}

class GeolocatorPositionSource implements StationPositionSource {
  const GeolocatorPositionSource();

  @override
  Future<String?> ensurePermission() async {
    if (!await Geolocator.isLocationServiceEnabled()) {
      return 'Location services are off. Turn them on to track the station.';
    }
    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }
    if (permission == LocationPermission.denied ||
        permission == LocationPermission.deniedForever) {
      return 'Precise location permission is needed to track the station.';
    }
    return null;
  }

  @override
  Future<TrackingFix> current() async {
    final p = await Geolocator.getCurrentPosition(
      locationSettings: const LocationSettings(
        accuracy: LocationAccuracy.best,
        timeLimit: Duration(seconds: 8),
      ),
    );
    return TrackingFix(p.latitude, p.longitude, p.accuracy, p.timestamp.toUtc());
  }
}

class StationTrackingController extends ChangeNotifier {
  static const maxAccuracyM = 50.0;

  StationTrackingController(
    this._api, {
    StationPositionSource? source,
    this.interval = const Duration(seconds: 5),
    DateTime Function()? now,
  }) : _source = source ?? const GeolocatorPositionSource(),
       _now = now ?? DateTime.now;

  final AuthApi _api;
  final StationPositionSource _source;
  final Duration interval;
  final DateTime Function() _now;

  List<TrackingSession> sessions = const [];
  TrackingSession? active;
  bool sending = false;
  int accepted = 0, rejected = 0;
  double? lastAccuracyM;
  DateTime? lastSentAt;
  DateTime? _lastCapturedAt;
  String? message;
  Timer? _timer;
  bool _busy = false, _disposed = false;
  int _generation = 0;

  bool get tracking => active != null;

  Future<void> refresh() async {
    final generation = _generation;
    try {
      final rows = await _api.request('station-tracking/active');
      if (generation != _generation) return;
      sessions = [
        for (final row in (rows as List? ?? const []))
          TrackingSession.fromJson(Map<String, dynamic>.from(row as Map)),
      ];
      if (active != null && !sessions.any((s) => s.id == active!.id)) {
        stop(reason: 'Tracking session ended by an administrator.');
      }
    } catch (_) {
      if (generation != _generation) return;
      sessions = const [];
    }
    _notify();
  }

  Future<void> start(TrackingSession session) async {
    if (active != null) return;
    final generation = _generation;
    final problem = await _source.ensurePermission();
    if (generation != _generation || active != null) return;
    if (problem != null) {
      message = problem;
      _notify();
      return;
    }
    active = session;
    accepted = rejected = 0;
    _lastCapturedAt = null;
    message = 'Tracking ${session.stationName}. Keep this phone with the station.';
    _notify();
    unawaited(_tick());
    _timer = Timer.periodic(interval, (_) => unawaited(_tick()));
  }

  void stop({String? reason}) {
    _timer?.cancel();
    _timer = null;
    active = null;
    sending = false;
    message = reason ?? 'Tracking stopped. The dashboard keeps the last known position.';
    _notify();
  }

  /// Account change or sign-out: stop reporting and forget this account's sessions.
  void reset() {
    _timer?.cancel();
    _timer = null;
    active = null;
    sending = false;
    sessions = const [];
    accepted = rejected = 0;
    lastAccuracyM = null;
    lastSentAt = null;
    _lastCapturedAt = null;
    message = null;
    _generation++;
    _notify();
  }

  Future<void> _tick() async {
    final session = active;
    if (session == null || _busy) return;
    if (session.expiresAt != null && !_now().toUtc().isBefore(session.expiresAt!)) {
      stop(reason: 'Tracking session expired.');
      return;
    }
    final generation = _generation;
    _busy = true;
    sending = true;
    _notify();
    try {
      final fix = await _source.current();
      if (generation != _generation || active?.id != session.id) return;
      // Android may hand back the previous fix until a new one is ready; it is not a
      // rejection, so it is neither uploaded nor counted.
      if (_lastCapturedAt != null && !fix.capturedAt.isAfter(_lastCapturedAt!)) return;
      lastAccuracyM = fix.accuracyM;
      if (fix.accuracyM > maxAccuracyM) {
        // The server rejects these too; skip the upload and keep waiting for a better fix.
        rejected++;
        message = 'Waiting for a better GPS fix (±${fix.accuracyM.round()} m).';
        return;
      }
      await _api.request(
        'station-tracking/${session.id}/positions',
        method: 'POST',
        body: {
          'latitude': fix.latitude,
          'longitude': fix.longitude,
          'accuracy_m': fix.accuracyM,
          'captured_at': fix.capturedAt.toUtc().toIso8601String(),
        },
      );
      if (generation != _generation || active?.id != session.id) return;
      accepted++;
      _lastCapturedAt = fix.capturedAt;
      lastSentAt = _now().toUtc();
      message = null;
    } on AccountException catch (error) {
      if (generation != _generation || active?.id != session.id) return;
      if (error.status == 409 && error.message.contains('not newer')) return;
      rejected++;
      message = error.message;
      // 404: not this account's session; 409 'not active': ended, expired or superseded.
      // A 409 for a fix that is not newer than the last one is only skipped.
      if (error.status == 404 ||
          (error.status == 409 && error.message.contains('not active'))) {
        stop(reason: 'Tracking session is no longer active.');
      }
    } catch (_) {
      if (generation != _generation || active?.id != session.id) return;
      rejected++;
      message = 'GPS fix unavailable; retrying.';
    } finally {
      _busy = false;
      sending = false;
      _notify();
    }
  }

  void _notify() {
    if (!_disposed) notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    _timer?.cancel();
    super.dispose();
  }
}
