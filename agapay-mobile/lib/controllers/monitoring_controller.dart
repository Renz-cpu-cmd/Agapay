import 'dart:async';

import 'package:flutter/foundation.dart';

import '../models/monitoring.dart';
import '../services/auth_api.dart';

class MonitoringController extends ChangeNotifier {
  MonitoringController(this._api);

  final AuthApi _api;
  Timer? _timer;
  int? _owner;
  bool _requesting = false;

  MonitoringSnapshot? snapshot;
  bool loading = false;
  String? error;

  List<MonitoringStation> get stations => snapshot?.stations ?? const [];
  MonitoringStation? get primary {
    for (final station in stations) {
      if (station.id == 'STATION_001') return station;
    }
    return stations.isEmpty ? null : stations.first;
  }

  void setOwner(int? owner) {
    if (_owner == owner) return;
    _owner = owner;
    _timer?.cancel();
    _timer = null;
    snapshot = null;
    error = null;
    loading = owner != null;
    notifyListeners();
    if (owner == null) return;
    unawaited(refresh());
    _timer = Timer.periodic(const Duration(seconds: 5), (_) => refresh());
  }

  Future<void> refresh() async {
    if (_owner == null || _requesting) return;
    _requesting = true;
    try {
      final raw = await _api.request('monitoring/stations?history_limit=120');
      if (_owner == null) return;
      snapshot = MonitoringSnapshot.fromJson(raw as Map<String, dynamic>);
      error = null;
    } catch (reason) {
      if (_owner != null) {
        error = reason is AccountException
            ? reason.message
            : 'Live monitoring is unavailable.';
      }
    } finally {
      _requesting = false;
      if (_owner != null) {
        loading = false;
        notifyListeners();
      }
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }
}
