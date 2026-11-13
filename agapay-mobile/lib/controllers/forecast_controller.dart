import '../core/release_configuration.dart';
import 'dart:async';
import 'package:flutter/foundation.dart';
import '../models/prediction.dart';
import '../services/auth_api.dart';

class ForecastController extends ChangeNotifier {
  ForecastController(this.api, {DateTime Function()? now})
    : now = now ?? DateTime.now;
  final AuthApi api;
  final DateTime Function() now;
  int? _owner;
  int _generation = 0;
  bool _disposed = false;
  bool _foreground = true;
  Timer? _poll, _expiry;
  DateTime? _deadline;
  String stationId = 'STATION_001';
  String scenario = 'available';
  bool preview = false, previewAllowed = false, loading = false;
  Prediction? data;
  String? error;
  bool get expired =>
      data?.status == 'available' &&
      (_deadline == null || !now().isBefore(_deadline!));
  bool get available =>
      data?.status == 'available' && !expired && error == null;
  void _notify() {
    if (!_disposed) notifyListeners();
  }

  void selectStation(String id) {
    if (_disposed || stationId == id) return;
    stationId = id;
    ++_generation;
    data = null;
    error = null;
    _deadline = null;
    _expiry?.cancel();
    loading = false;
    _notify();
    if (_owner != null) unawaited(refresh());
  }

  void setForeground(bool value) {
    if (_disposed || _foreground == value) return;
    _foreground = value;
    ++_generation;
    _poll?.cancel();
    _expiry?.cancel();
    loading = false;
    if (!value) {
      error = 'Forecast reads paused.';
      _notify();
      return;
    }
    _notify();
    if (_owner != null) {
      _poll = Timer.periodic(const Duration(seconds: 30), (_) {
        if (!loading) unawaited(refresh());
      });
      unawaited(refresh());
    }
  }

  Future<void> setOwner(int? owner) async {
    if (_owner == owner) return;
    ++_generation;
    _owner = owner;
    stationId = "STATION_001";
    _poll?.cancel();
    _expiry?.cancel();
    data = null;
    error = null;
    loading = false;
    preview = false;
    previewAllowed = false;
    scenario = 'available';
    _deadline = null;
    _notify();
    if (owner == null) return;
    if (_foreground) {
      _poll = Timer.periodic(const Duration(seconds: 30), (_) {
        if (!loading) refresh();
      });
    }
    await refresh();
  }

  Future<void> setPreview(bool value, {String? scenario}) async {
    if (value && !ReleaseConfiguration.exercisesAvailable) return;
    if (value && !previewAllowed) return;
    if (scenario != null && !forecastLabels.containsKey(scenario)) return;
    ++_generation;
    loading = false;
    preview = value;
    this.scenario = scenario ?? this.scenario;
    data = null;
    _expiry?.cancel();
    _deadline = null;
    error = null;
    _notify();
    await refresh();
  }

  Future<void> refresh() async {
    if (_owner == null || _disposed || !_foreground || loading) return;
    final generation = ++_generation;
    final started = now();
    final requestedPreview = preview;
    loading = true;
    _notify();
    try {
      final response = await api.request(
        'predictions/$stationId?mode=${preview ? 'preview' : 'actual'}&scenario=$scenario',
      );
      final json = response as Map<String, dynamic>;
      final prediction = requestedPreview
          ? Prediction.fromJson(json)
          : Prediction.fromPublishedJson(json);
      if (prediction.stationId != stationId ||
          (requestedPreview
              ? prediction.source != 'simulated'
              : prediction.source == 'simulated')) {
        throw const FormatException('Unexpected station or forecast source.');
      }
      if (_disposed || generation != _generation) return;
      data = prediction;
      error = null;
      previewAllowed = prediction.previewAllowed;
      _expiry?.cancel();
      // Base validity on the server's relative TTL; subtract request travel time.
      _deadline = prediction.validUntil == null
          ? null
          : started.add(
              prediction.validUntil!.difference(prediction.checkedAt),
            );
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
          : 'The forecast response could not be validated. Please retry.';
    } finally {
      if (!_disposed && generation == _generation) {
        loading = false;
        _notify();
      }
    }
  }

  @override
  void dispose() {
    _disposed = true;
    ++_generation;
    _poll?.cancel();
    _expiry?.cancel();
    super.dispose();
  }
}
