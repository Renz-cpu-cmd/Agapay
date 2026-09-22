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

  Future<void> setOwner(int? owner) async {
    if (_owner == owner) return;
    ++_generation;
    _owner = owner;
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
    _poll = Timer.periodic(const Duration(seconds: 30), (_) {
      if (!loading) refresh();
    });
    await refresh();
  }

  Future<void> setPreview(bool value, {String? scenario}) async {
    if (value && !previewAllowed) return;
    if (scenario != null && !forecastLabels.containsKey(scenario)) return;
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
    if (_owner == null || _disposed) return;
    final generation = ++_generation;
    final started = now();
    final requestedPreview = preview;
    loading = true;
    _notify();
    try {
      final response = await api.request(
        'predictions/$stationId?mode=${preview ? 'preview' : 'actual'}&scenario=$scenario',
      );
      final prediction = Prediction.fromJson(response as Map<String, dynamic>);
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
