Map<String, dynamic> predictionFixture({
  String status = 'not_trained',
  String source = 'none',
  DateTime? now,
}) {
  final at = (now ?? DateTime.now()).toUtc();
  return {
    'schema_version': '1.0',
    if (source == 'model' && status == 'available') ...{
      'forecast_id': '00000000-0000-4000-8000-000000000001',
      'deployment_version': 1,
      'configuration_hash': 'a' * 64,
      'model_card_id': 'b' * 64,
      'reference_datum': 'Synthetic test datum',
      'data_cutoff': at.toIso8601String(),
      'measurement_source': 'registry_verified_physical_device',
      'ingress_identity': 'SYNTHETIC_DEVICE',
      'registry_version': 1,
      'uncertainty': {
        'method': 'calibration_event_max_absolute_residual_all_horizons',
        'nominal_coverage': .9,
        'withheld_event_coverage': .9,
        'calibration_events': 10,
        'test_events': 10,
        'policy_sha256': 'd' * 64,
        'display_resolution_cm': 2,
      },
    },
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
    'model_version': source == 'model' ? 'b' * 64 : null,
    'preview_allowed': true,
    'input_status': 'usable',
    'sample_count': 12,
    'valid_sample_count': 12,
    'timestamp_basis': source == 'simulated'
        ? 'synthetic'
        : source == 'model'
        ? 'device_measured'
        : 'server_received',
    'rainfall_interval_seconds': null,
    'forecasts': [
      for (var i = 0; i < 3; i++)
        {
          'horizon_minutes': (i + 1) * 30,
          'water_depth_cm': status == 'available' ? 96.0 + 3 * i : null,
          if (source == 'model' && status == 'available') ...{
            'lower_depth_cm': 94.0 + 3 * i,
            'upper_depth_cm': 98.0 + 3 * i,
          },
          'target_at': status == 'available'
              ? at.add(Duration(minutes: (i + 1) * 30)).toIso8601String()
              : null,
        },
    ],
  };
}
