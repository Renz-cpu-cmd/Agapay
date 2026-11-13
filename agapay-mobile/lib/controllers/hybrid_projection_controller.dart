import 'dart:async';
import 'package:flutter/foundation.dart';
import '../services/auth_api.dart';

/// Strict, display-only view of the experimental basin projection.
class HybridProjection {
  HybridProjection(this.json) {
    if (!['available', 'unavailable'].contains(json['status']) ||
        json['advisory_only'] != true ||
        json['station_id'] is! String) {
      throw const FormatException('Invalid hybrid projection metadata.');
    }
    checkedAt = DateTime.parse(json['checked_at'] as String);
    if (available) {
      final until = DateTime.parse(json['valid_until'] as String);
      if (!until.isAfter(checkedAt) ||
          (json['model_version'] as String?)?.isNotEmpty != true) {
        throw const FormatException('Incomplete hybrid projection metadata.');
      }
      final rows = json['points'] as List;
      if (rows.length != 3) throw const FormatException('Missing horizons.');
      final nowDepth = (json['adjusted'] as Map)['depth_cm'];
      if (!_depth(nowDepth)) {
        throw const FormatException('Invalid starting depth.');
      }
      for (var i = 0; i < 3; i++) {
        final point = rows[i] as Map;
        if (point['horizon_minutes'] != [30, 60, 90][i] ||
            !_depth(point['depth_cm']) ||
            !DateTime.parse(point['target_at'] as String).isAfter(checkedAt)) {
          throw const FormatException('Invalid hybrid horizon.');
        }
      }
    } else if ((json['points'] as List).isNotEmpty) {
      throw const FormatException('Unavailable projection has numeric points.');
    }
  }
  final Map<String, dynamic> json;
  late final DateTime checkedAt;
  bool get available => json['status'] == 'available';
  String get stationId => json['station_id'] as String;
  String get reason => json['reason'] as String? ?? 'Projection unavailable.';
  List<double> get depths => available
      ? [
          ((json['adjusted'] as Map)['depth_cm'] as num).toDouble(),
          for (final p in json['points'] as List)
            (p['depth_cm'] as num).toDouble(),
        ]
      : const [];
  Map<String, dynamic>? get rain =>
      (json['rain_activity'] ?? json['rain_snapshot']) as Map<String, dynamic>?;
  bool get historical =>
      (json['rainfall_source'] as String? ?? '').contains('historical-context');
  static bool _depth(dynamic n) =>
      n is num && n.isFinite && n >= 0 && n <= 1000;
}

class HybridProjectionController extends ChangeNotifier {
  HybridProjectionController(this.api, {DateTime Function()? now})
    : now = now ?? DateTime.now;
  final AuthApi api;
  final DateTime Function() now;
  int? _owner;
  int _generation = 0;
  bool _disposed = false;
  bool _foreground = true;
  int? _requestGeneration;
  bool loading = false;
  String stationId = 'STATION_001';
  HybridProjection? data;
  String? error;
  DateTime? _deadline, _serverAt, _receivedAt;
  Timer? _poll, _expiry;
  DateTime get serverNow => _serverAt == null
      ? now().toUtc()
      : _serverAt!.add(now().difference(_receivedAt!));
  bool get expired =>
      data?.available == true &&
      (_deadline == null || !now().isBefore(_deadline!));
  bool get available =>
      _foreground && data?.available == true && !expired && error == null;
  bool get gaugeFresh {
    final rain = error == null ? data?.rain : null;
    final at = DateTime.tryParse(rain?['last_received_at'] as String? ?? '');
    return _foreground &&
        rain?['source_trusted'] == true &&
        rain?['station_id'] == stationId &&
        rain?['data_source'] == 'physical_rain_gauge' &&
        rain?['connected'] == true &&
        at != null &&
        !serverNow.isBefore(at) &&
        serverNow.difference(at) <= const Duration(seconds: 30);
  }

  double? get currentRainMm {
    if (!gaugeFresh) return null;
    final rain = data!.rain!;
    final start = DateTime.tryParse(
      rain['current_hour_start'] as String? ?? '',
    );
    final at = serverNow.toUtc();
    final value = rain['incomplete_hour_mm'];
    return start == DateTime.utc(at.year, at.month, at.day, at.hour) &&
            value is num &&
            value.isFinite &&
            value >= 0
        ? value.toDouble()
        : null;
  }

  List<DateTime?> get rainfallTimes {
    final rows = gaugeFresh
        ? data!.rain!['completed_hours']
        : available && data!.historical
        ? data!.json['rainfall_history']
        : null;
    if (rows is! List) return const [];
    return rows
        .take(24)
        .map((row) => DateTime.tryParse(row['timestamp_utc'] as String? ?? ''))
        .toList();
  }

  List<double?> get rainfallHours {
    final rows = gaugeFresh
        ? data!.rain!['completed_hours']
        : available && data!.historical
        ? data!.json['rainfall_history']
        : null;
    if (rows is! List) return const [];
    return rows.take(24).map<double?>((r) {
      final n = r['rainfall_mm'];
      return r['valid'] == true &&
              r['interval_seconds'] == 3600 &&
              n is num &&
              n.isFinite &&
              n >= 0
          ? n.toDouble()
          : null;
    }).toList();
  }

  void _notify() {
    if (!_disposed) notifyListeners();
  }

  void _clear() {
    ++_generation;
    _poll?.cancel();
    _expiry?.cancel();
    data = null;
    error = null;
    _deadline = null;
    _serverAt = null;
    _receivedAt = null;
    loading = false;
  }

  void setForeground(bool value) {
    if (_disposed || _foreground == value) return;
    _foreground = value;
    ++_generation;
    _poll?.cancel();
    _expiry?.cancel();
    if (!value) {
      error = 'Live projection reads paused.';
      _notify();
      return;
    }
    _notify();
    if (!loading && _owner != null) unawaited(refresh());
  }

  void setOwner(int? owner) {
    if (_owner == owner) return;
    _clear();
    _owner = owner;
    stationId = 'STATION_001';
    _notify();
    if (owner != null) unawaited(refresh());
  }

  void selectStation(String id) {
    if (stationId == id) return;
    _clear();
    stationId = id;
    _notify();
    unawaited(refresh());
  }

  Future<void> refresh() async {
    if (_owner == null || _disposed || loading || !_foreground) return;
    _poll?.cancel();
    final generation = _generation;
    _requestGeneration = generation;
    final station = stationId;
    final started = now();
    loading = true;
    _notify();
    try {
      final raw = await api.request(
        'rain-activity/${Uri.encodeComponent(station)}',
      );
      final result = HybridProjection(raw as Map<String, dynamic>);
      if (raw['workspace'] != 'observations_only' || result.available) {
        throw const FormatException(
          'Operational rain reads cannot contain private projections.',
        );
      }
      if (result.stationId != station) {
        throw const FormatException('Wrong projection station.');
      }
      if (result.available &&
          result.json['mode'] == 'live' &&
          (result.rain?['station_id'] != station ||
              result.rain?['data_source'] != 'physical_rain_gauge')) {
        throw const FormatException('Wrong rainfall station or source.');
      }
      if (_disposed || generation != _generation) return;
      data = result;
      error = null;
      _expiry?.cancel();
      _serverAt = result.checkedAt;
      _receivedAt = started;
      _deadline = result.available
          ? started.add(
              DateTime.parse(
                raw['valid_until'] as String,
              ).difference(result.checkedAt),
            )
          : null;
      if (_deadline != null && now().isBefore(_deadline!)) {
        _expiry = Timer(_deadline!.difference(now()), _notify);
      }
    } catch (e) {
      if (_disposed || generation != _generation) return;
      data = null;
      _deadline = null;
      _expiry?.cancel();
      error = e is AccountException
          ? e.message
          : 'The projection response could not be validated.';
    } finally {
      if (!_disposed &&
          _requestGeneration == generation &&
          generation != _generation) {
        loading = false;
        if (_foreground && _owner != null) unawaited(refresh());
      }
      if (!_disposed && generation == _generation) {
        loading = false;
        _notify();
        if (_foreground) {
          _poll = Timer(Duration(seconds: error == null ? 3 : 15), refresh);
        }
      }
    }
  }

  @override
  void dispose() {
    _disposed = true;
    _clear();
    super.dispose();
  }
}
