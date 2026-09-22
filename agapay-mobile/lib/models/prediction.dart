const forecastLabels = {
  'not_trained': 'Model not trained',
  'insufficient_data': 'Insufficient history',
  'stale_data': 'Readings are stale',
  'invalid_data': 'Invalid readings',
  'available': 'Forecast available',
  'service_error': 'Service unavailable',
};

class ForecastPoint {
  ForecastPoint(this.horizonMinutes, this.waterDepthCm, this.targetAt);
  final int horizonMinutes;
  final double? waterDepthCm;
  final DateTime? targetAt;
}

class Prediction {
  Prediction._(
    this.stationId,
    this.status,
    this.reason,
    this.source,
    this.checkedAt,
    this.generatedAt,
    this.validUntil,
    this.latestInputAt,
    this.modelVersion,
    this.previewAllowed,
    this.points,
  );
  final String stationId, status, reason, source;
  final DateTime checkedAt;
  final DateTime? generatedAt, validUntil, latestInputAt;
  final String? modelVersion;
  final bool previewAllowed;
  final List<ForecastPoint> points;

  factory Prediction.fromJson(Map<String, dynamic> json) {
    DateTime? date(dynamic value) =>
        value == null ? null : DateTime.parse(value as String);
    final status = json['status'] as String;
    final source = json['source'] as String;
    if (json['schema_version'] != '1.0' ||
        json['advisory_only'] != true ||
        !forecastLabels.containsKey(status) ||
        !['none', 'model', 'simulated'].contains(source)) {
      throw const FormatException('Unsupported prediction response.');
    }
    final rows = json['forecasts'] as List;
    if (rows.length != 3) {
      throw const FormatException('Missing forecast horizons.');
    }
    final points = <ForecastPoint>[];
    for (var i = 0; i < 3; i++) {
      final row = rows[i] as Map<String, dynamic>;
      final value = (row['water_depth_cm'] as num?)?.toDouble();
      final target = date(row['target_at']);
      if (row['horizon_minutes'] != [30, 60, 90][i]) {
        throw const FormatException('Unexpected forecast horizon.');
      }
      if (status == 'available'
          ? value == null ||
                !value.isFinite ||
                value < 0 ||
                value > 1000 ||
                target == null
          : value != null || target != null) {
        throw const FormatException('Invalid forecast values.');
      }
      points.add(ForecastPoint(row['horizon_minutes'] as int, value, target));
    }
    final checked = date(json['checked_at'])!;
    final generated = date(json['generated_at']);
    final until = date(json['valid_until']);
    final latest = date(json['input_last_recorded_at']);
    final version = json['model_version'] as String?;
    if (status == 'available' &&
        (source == 'none' ||
            generated == null ||
            until == null ||
            !until.isAfter(checked) ||
            latest == null ||
            (source == 'model' && (version == null || version.isEmpty)))) {
      throw const FormatException('Incomplete forecast metadata.');
    }
    if (source == 'simulated' && version != null) {
      throw const FormatException(
        'Simulated response claimed a trained model.',
      );
    }
    return Prediction._(
      json['station_id'] as String,
      status,
      json['reason'] as String,
      source,
      checked,
      generated,
      until,
      latest,
      version,
      json['preview_allowed'] as bool,
      points,
    );
  }
}

String predictionTime(DateTime? date) {
  if (date == null) return '—';
  final t = date.toLocal();
  String two(int n) => n.toString().padLeft(2, '0');
  return '${t.month}/${t.day} ${two(t.hour)}:${two(t.minute)}';
}
