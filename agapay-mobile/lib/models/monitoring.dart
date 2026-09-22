import 'alert_level.dart';

class MonitoringSample {
  MonitoringSample.fromJson(Map<String, dynamic> json)
    : sequenceNo = json['sequence_no'] as int,
      waterDepthCm = (json['water_depth_cm'] as num?)?.toDouble(),
      rainfallMm = (json['rainfall_mm'] as num).toDouble(),
      sensorQuality = json['sensor_quality'] as String,
      recordedAt = DateTime.parse(json['recorded_at'] as String).toLocal();

  final int sequenceNo;
  final double? waterDepthCm;
  final double rainfallMm;
  final String sensorQuality;
  final DateTime recordedAt;
}

class MonitoringStation {
  MonitoringStation.fromJson(Map<String, dynamic> json)
    : id = json['station_id'] as String,
      name = json['station_name'] as String,
      barangay = (json['barangay'] as String?) ?? 'Barangay unavailable',
      municipality = (json['municipality'] as String?) ?? 'Urdaneta City',
      latitude = (json['latitude'] as num?)?.toDouble(),
      longitude = (json['longitude'] as num?)?.toDouble(),
      connectionStatus = json['connection_status'] as String,
      isOnline = json['is_online'] as bool,
      isStale = json['is_stale'] as bool,
      ageSeconds = json['age_seconds'] as int?,
      alertLevel = _alert(json['alert_tier'] as String?),
      trend = json['trend'] as String,
      currentDepthCm = (json['current_depth_cm'] as num?)?.toDouble(),
      latestDepthCm = (json['latest_depth_cm'] as num?)?.toDouble(),
      latestRainfallMm = (json['latest_rainfall_mm'] as num?)?.toDouble(),
      sensorQuality = json['sensor_quality'] as String?,
      observedAt = _time(json['observed_at']),
      firmwareVersion = json['firmware_version'] as String?,
      source = json['source'] as String,
      thresholdAdvisoryCm = (json['threshold_advisory_cm'] as num).toDouble(),
      thresholdWarningCm = (json['threshold_warning_cm'] as num).toDouble(),
      thresholdEvacuateCm = (json['threshold_evacuate_cm'] as num).toDouble(),
      history = (json['history'] as List<dynamic>)
          .map(
            (value) => MonitoringSample.fromJson(value as Map<String, dynamic>),
          )
          .toList(growable: false);

  final String id, name, barangay, municipality;
  final double? latitude, longitude;
  final String connectionStatus, trend, source;
  final bool isOnline, isStale;
  final int? ageSeconds;
  final AlertLevel? alertLevel;
  final double? currentDepthCm, latestDepthCm, latestRainfallMm;
  final String? sensorQuality, firmwareVersion;
  final DateTime? observedAt;
  final double thresholdAdvisoryCm, thresholdWarningCm, thresholdEvacuateCm;
  final List<MonitoringSample> history;

  bool get isSimulator => source == 'simulator';
  bool get hasValidReading => currentDepthCm != null;

  static AlertLevel? _alert(String? value) => switch (value) {
    'NORMAL' => AlertLevel.normal,
    'ADVISORY' => AlertLevel.advisory,
    'WARNING' => AlertLevel.warning,
    'EVACUATE' => AlertLevel.evacuate,
    _ => null,
  };

  static DateTime? _time(dynamic value) =>
      value is String ? DateTime.tryParse(value)?.toLocal() : null;
}

class MonitoringSnapshot {
  MonitoringSnapshot.fromJson(Map<String, dynamic> json)
    : checkedAt = DateTime.parse(json['checked_at'] as String).toLocal(),
      staleAfterSeconds = json['stale_after_seconds'] as int,
      stations = (json['stations'] as List<dynamic>)
          .map(
            (value) =>
                MonitoringStation.fromJson(value as Map<String, dynamic>),
          )
          .toList(growable: false);

  final DateTime checkedAt;
  final int staleAfterSeconds;
  final List<MonitoringStation> stations;
}
