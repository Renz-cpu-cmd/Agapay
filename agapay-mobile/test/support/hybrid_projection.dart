Map<String, dynamic> hybridFixture({
  String station = 'STATION_001',
  DateTime? at,
}) {
  final now = (at ?? DateTime.now()).toUtc();
  return {
    'station_id': station,
    'status': 'available',
    'advisory_only': true,
    'checked_at': now.toIso8601String(),
    'valid_until': now.add(const Duration(seconds: 5)).toIso8601String(),
    'model_version': 'test-fixture',
    'mode': 'live',
    'rainfall_source': 'historical-context demonstration',
    'adjusted': {'depth_cm': 20},
    'initialization_at': now.toIso8601String(),
    'points': [
      for (var i = 0; i < 3; i++)
        {
          'horizon_minutes': (i + 1) * 30,
          'depth_cm': 21.0 + i,
          'target_at': now
              .add(Duration(minutes: (i + 1) * 30))
              .toIso8601String(),
        },
    ],
    'rain_activity': {
      'station_id': station,
      'data_source': 'physical_rain_gauge',
      'connected': true,
      'source_trusted': true,
      'last_received_at': now.toIso8601String(),
      'current_hour_start': DateTime.utc(
        now.year,
        now.month,
        now.day,
        now.hour,
      ).toIso8601String(),
      'incomplete_hour_mm': .7,
      'ml_ready': false,
      'completed_hours': [
        {
          'timestamp_utc': now
              .subtract(const Duration(hours: 1))
              .toIso8601String(),
          'rainfall_mm': null,
          'interval_seconds': 3600,
          'valid': false,
        },
        {
          'timestamp_utc': now.toIso8601String(),
          'rainfall_mm': 0,
          'interval_seconds': 3600,
          'valid': true,
        },
      ],
    },
  };
}

Map<String, dynamic> rainActivityFixture({
  String station = 'STATION_001',
  DateTime? at,
}) {
  final data = hybridFixture(station: station, at: at);
  return {
    'workspace': 'observations_only',
    'station_id': station,
    'status': 'unavailable',
    'advisory_only': true,
    'checked_at': data['checked_at'],
    'reason': 'Rain observations only',
    'points': <dynamic>[],
    'rain_activity': data['rain_activity'],
  };
}
