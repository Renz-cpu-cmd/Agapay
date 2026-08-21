import '../models/station.dart';
import '../models/telemetry_history.dart';
import '../services/mock_data.dart';

abstract class StationRepository {
  Future<List<Station>> getStations();
  Future<Station> getStationById(String id);
  Future<TelemetrySummary> getStationTelemetryHistory(String stationId, {int hoursBack = 24});
}

class MockStationRepository implements StationRepository {
  List<Station> _stations = List.from(MockData.initialStations);

  @override
  Future<List<Station>> getStations() async {
    await Future.delayed(const Duration(milliseconds: 250));
    return List.unmodifiable(_stations);
  }

  @override
  Future<Station> getStationById(String id) async {
    await Future.delayed(const Duration(milliseconds: 150));
    return _stations.firstWhere(
      (s) => s.id == id,
      orElse: () => _stations.first,
    );
  }

  @override
  Future<TelemetrySummary> getStationTelemetryHistory(String stationId, {int hoursBack = 24}) async {
    await Future.delayed(const Duration(milliseconds: 300));
    return MockData.getHistoricalSummary(stationId, hoursBack);
  }

  void updateStation(Station updated) {
    final index = _stations.indexWhere((s) => s.id == updated.id);
    if (index != -1) {
      _stations[index] = updated;
    }
  }
}
