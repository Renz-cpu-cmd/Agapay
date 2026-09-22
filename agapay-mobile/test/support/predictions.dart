Map<String, dynamic> predictionFixture({
  String status = 'not_trained',
  String source = 'none',
  DateTime? now,
}) {
  final at = (now ?? DateTime.now()).toUtc();
  return {
    'schema_version': '1.0',
    'station_id': 'STATION_001',
    'status': status,
    'reason': source == 'simulated'
        ? 'Sample response for interface testing.'
        : 'A trained forecast model is not configured.',
    'source': source,
    'advisory_only': true,
    'checked_at': at.toIso8601String(),
    'generated_at': status == 'available' ? at.toIso8601String() : null,
    'valid_until': status == 'available'
        ? at.add(const Duration(seconds: 60)).toIso8601String()
        : null,
    'input_last_recorded_at': at.toIso8601String(),
    'input_window_start': at
        .subtract(const Duration(minutes: 55))
        .toIso8601String(),
    'model_version': source == 'model' ? 'test-only' : null,
    'preview_allowed': true,
    'input_status': 'usable',
    'sample_count': 12,
    'valid_sample_count': 12,
    'timestamp_basis': source == 'simulated' ? 'synthetic' : 'server_received',
    'rainfall_interval_seconds': null,
    'forecasts': [
      for (var i = 0; i < 3; i++)
        {
          'horizon_minutes': (i + 1) * 30,
          'water_depth_cm': status == 'available' ? 96.0 + 3 * i : null,
          'target_at': status == 'available'
              ? at.add(Duration(minutes: (i + 1) * 30)).toIso8601String()
              : null,
        },
    ],
  };
}
