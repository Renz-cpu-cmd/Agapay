import 'dart:async';

import 'package:flutter/foundation.dart';

import '../models/monitoring.dart';
import '../services/auth_api.dart';

class MonitoringController extends ChangeNotifier {
  MonitoringController(this._api, {DateTime Function()? now})
    : now = now ?? DateTime.now;
  final DateTime Function() now;

  final AuthApi _api;
  Timer? _timer;
  int? _owner;
  bool _requesting = false;
  bool _foreground = true;
  int? _requestGeneration;
  int _generation = 0;
  String selectedStationId = 'STATION_001';

  MonitoringSnapshot? snapshot;
  bool loading = false;
  String? error;

  List<MonitoringStation> get stations => snapshot?.stations ?? const [];
  MonitoringStation? get primary {
    for (final station in stations) {
      if (station.id == selectedStationId) return station;
    }
    return stations.isEmpty ? null : stations.first;
  }

  List<StationFreshnessView> get views {
    final at = now();
    return List.unmodifiable(stations.map((s) => view(s, at: at)));
  }

  StationFreshnessView? get primaryView =>
      primary == null ? null : view(primary!);
  StationFreshnessView view(MonitoringStation station, {DateTime? at}) {
    final instant = at ?? now(), checked = snapshot?.checkedAt;
    int? age(int? value) {
      if (value == null ||
          value < 0 ||
          checked == null ||
          instant.isBefore(checked.subtract(const Duration(minutes: 1)))) {
        return null;
      }
      return value + instant.difference(checked).inSeconds.clamp(0, 2147483647);
    }

    final heartbeatAge = age(station.heartbeatAgeSeconds),
        depthAge = age(station.depthAgeSeconds),
        rainAge = age(station.rainfallAgeSeconds),
        limit = snapshot?.staleAfterSeconds ?? 0;
    final online =
        error == null &&
        station.isOnline &&
        station.heartbeatFresh &&
        heartbeatAge != null &&
        heartbeatAge <= limit;
    final trusted =
        station.sourceTrusted &&
        station.depthSourceTrusted &&
        station.sourceClass == 'physical_device' &&
        station.stream == 'operational';
    final fresh =
        trusted &&
        !station.hazardReviewRequired &&
        station.sensorQuality == 'valid' &&
        station.hasValidReading &&
        online &&
        station.depthFresh &&
        depthAge != null &&
        depthAge <= limit;
    final rainFresh =
        error == null &&
        station.rainfallFresh &&
        rainAge != null &&
        rainAge <= 30;
    final status = station.hazardReviewRequired
        ? 'REVIEW REQUIRED'
        : (!station.sourceTrusted ||
              (station.hasValidReading && !station.depthSourceTrusted))
        ? 'UNREGISTERED SOURCE'
        : station.isSimulator
        ? 'VIRTUAL STATION'
        : fresh
        ? 'LIVE'
        : station.hasValidReading
        ? 'STALE READING'
        : 'WAITING FOR DATA';
    return StationFreshnessView(
      station: station,
      asOf: instant,
      sourceLabel: station.hasValidReading && !station.depthSourceTrusted
          ? 'Unregistered depth source'
          : station.sourceLabel,
      sourceStatus: status,
      hazardState: !fresh && station.activeHazardTier != null
          ? 'unresolved'
          : station.hazardState,
      depth: ChannelFreshness(
        value: station.currentDepthCm,
        measuredAt: station.lastValidDepthAt,
        ageSeconds: depthAge,
        status: fresh
            ? 'fresh'
            : !station.hasValidReading
            ? 'missing'
            : station.sensorQuality == 'invalid'
            ? 'invalid / retained'
            : 'retained / stale',
        quality: station.sensorQuality ?? 'unknown',
        source: station.depthSourceTrusted
            ? station.sourceLabel
            : 'Unregistered depth source',
        fresh: fresh,
      ),
      heartbeat: ChannelFreshness(
        value: null,
        measuredAt: station.heartbeatAt,
        ageSeconds: heartbeatAge,
        status: online
            ? 'online'
            : error != null
            ? 'unconfirmed'
            : [
                'maintenance',
                'inactive',
                'no_data',
              ].contains(station.connectionStatus)
            ? station.connectionStatus
            : 'offline',
        quality: station.connectionStatus,
        source: station.sourceLabel,
        fresh: online,
      ),
      rain: ChannelFreshness(
        value: station.latestRainfallMm,
        measuredAt: DateTime.tryParse(
          station.rainfallProduct?['interval_end'] as String? ?? '',
        ),
        ageSeconds: rainAge,
        status: rainFresh
            ? 'fresh'
            : station.latestRainfallMm == null
            ? 'missing'
            : 'retained / stale',
        quality:
            station.rainfallProduct?['quality']?.toString() ??
            station.rainfallProduct?['coverage']?.toString() ??
            'unknown',
        source: station.rainfallProduct?['source']?.toString() ?? 'unverified',
        fresh: rainFresh,
      ),
    );
  }

  bool isFresh(MonitoringStation station) => view(station).depth.fresh;
  bool isOnline(MonitoringStation station) => view(station).heartbeat.fresh;
  bool isRainFresh(MonitoringStation station) => view(station).rain.fresh;
  int? depthAge(MonitoringStation station) => view(station).depth.ageSeconds;
  int? heartbeatAge(MonitoringStation station) =>
      view(station).heartbeat.ageSeconds;
  String measurementAgeLabel(MonitoringStation station) =>
      ageLabel(depthAge(station));
  static String ageLabel(int? seconds) {
    if (seconds == null) return 'Unknown';
    if (seconds < 60) return '$seconds sec ago';
    final minutes = seconds ~/ 60;
    if (minutes < 60) return '$minutes min ago';
    final hours = minutes ~/ 60;
    return '$hours hr${hours == 1 ? '' : 's'} ago';
  }

  void selectStation(String id) {
    if (selectedStationId == id || !stations.any((s) => s.id == id)) return;
    selectedStationId = id;
    notifyListeners();
  }

  void setForeground(bool value) {
    if (_foreground == value) return;
    _foreground = value;
    ++_generation;
    _timer?.cancel();
    if (!value) {
      error = 'Live reads paused. Last-known timestamps are retained.';
      notifyListeners();
      return;
    }
    notifyListeners();
    if (_owner != null) {
      _startTimer();
      if (!_requesting) unawaited(refresh());
    }
  }

  void _startTimer() {
    _timer?.cancel();
    if (!_foreground || _owner == null) return;
    _timer = Timer.periodic(const Duration(seconds: 1), (timer) {
      notifyListeners();
      if (timer.tick % 5 == 0) unawaited(refresh());
    });
  }

  void setOwner(int? owner) {
    if (_owner == owner) return;
    _owner = owner;
    ++_generation;
    _requesting = false;
    _requestGeneration = null;
    selectedStationId = 'STATION_001';
    _timer?.cancel();
    _timer = null;
    snapshot = null;
    error = null;
    loading = owner != null;
    notifyListeners();
    if (owner == null) return;
    unawaited(refresh());
    _startTimer();
  }

  Future<void> refresh() async {
    if (_owner == null || _requesting || !_foreground) return;
    _requesting = true;
    final generation = _generation;
    _requestGeneration = generation;
    try {
      final raw = await _api.request('monitoring/stations?history_limit=20');
      if (_owner == null || generation != _generation) return;
      snapshot = MonitoringSnapshot.fromJson(raw as Map<String, dynamic>);
      error = _api.wasCached('monitoring/stations?history_limit=20')
          ? 'OFFLINE · LAST KNOWN. Current measurements and connectivity are unconfirmed.'
          : null;
    } catch (reason) {
      if (_owner != null && generation == _generation) {
        error = reason is AccountException
            ? reason.message
            : 'Live monitoring is unavailable.';
      }
    } finally {
      if (_requestGeneration == generation) {
        _requesting = false;
        if (_foreground && _owner != null && generation != _generation) {
          unawaited(refresh());
        }
      }
      if (_owner != null && generation == _generation) {
        loading = false;
        notifyListeners();
      }
    }
  }

  @override
  void dispose() {
    ++_generation;
    _timer?.cancel();
    super.dispose();
  }
}
