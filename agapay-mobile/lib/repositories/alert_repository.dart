import '../models/flood_alert.dart';
import '../services/mock_data.dart';

abstract class AlertRepository {
  Future<List<FloodAlert>> getActiveAlerts();
  Future<FloodAlert?> getLatestAlert();
  Future<void> acknowledgeAlert(String alertId);
}

class MockAlertRepository implements AlertRepository {
  List<FloodAlert> _alerts = List.from(MockData.initialAlerts);

  @override
  Future<List<FloodAlert>> getActiveAlerts() async {
    await Future.delayed(const Duration(milliseconds: 200));
    return List.unmodifiable(_alerts);
  }

  @override
  Future<FloodAlert?> getLatestAlert() async {
    await Future.delayed(const Duration(milliseconds: 150));
    if (_alerts.isEmpty) return null;
    return _alerts.first;
  }

  @override
  Future<void> acknowledgeAlert(String alertId) async {
    await Future.delayed(const Duration(milliseconds: 100));
    final index = _alerts.indexWhere((a) => a.id == alertId);
    if (index != -1) {
      _alerts[index] = _alerts[index].copyWith(isAcknowledged: true);
    }
  }
}
