import 'forecast_contract.generated.dart';

const forecastLabels = {
  'unavailable': 'Forecast unavailable',
  'not_trained': 'Model not trained',
  'insufficient_data': 'Insufficient history',
  'stale_data': 'Readings are stale',
  'invalid_data': 'Invalid readings',
  'available': 'Forecast available',
  'service_error': 'Service unavailable',
};

class ForecastPoint {
  ForecastPoint(
    this.horizonMinutes,
    this.waterDepthCm,
    this.targetAt, [
    this.lowerDepthCm,
    this.upperDepthCm,
  ]);
  final int horizonMinutes;
  final double? waterDepthCm;
  final DateTime? targetAt;
  final double? lowerDepthCm, upperDepthCm;
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
    this.points, {
    this.publication = const {},
  });
  final String stationId, status, reason, source;
  final DateTime checkedAt;
  final DateTime? generatedAt, validUntil, latestInputAt;
  final String? modelVersion;
  final bool previewAllowed;
  final List<ForecastPoint> points;
  final Map<String, dynamic> publication;

  factory Prediction.fromPublishedJson(Map<String, dynamic> json) {
    final data = Prediction.fromJson(json);
    if (data.status == 'available' &&
        (!data.checkedAt.isUtc ||
            data.generatedAt == null ||
            !data.generatedAt!.isUtc ||
            data.latestInputAt == null ||
            !data.latestInputAt!.isUtc ||
            data.latestInputAt!.isAfter(data.generatedAt!) ||
            data.generatedAt!.isAfter(data.checkedAt))) {
      throw const FormatException(
        'Published timestamps require aware, causal metadata.',
      );
    }
    if (data.status == 'available') {
      final raw = json['uncertainty'];
      if (raw is! Map<String, dynamic>) {
        throw const FormatException('Missing calibrated uncertainty.');
      }
      bool finite(dynamic value) => value is num && value.isFinite;
      if (raw['method'] !=
              'calibration_event_max_absolute_residual_all_horizons' ||
          !finite(raw['nominal_coverage']) ||
          raw['nominal_coverage'] < .8 ||
          raw['nominal_coverage'] > .99 ||
          !finite(raw['withheld_event_coverage']) ||
          raw['withheld_event_coverage'] < 0 ||
          raw['withheld_event_coverage'] > 1 ||
          raw['calibration_events'] is! int ||
          raw['calibration_events'] < 1 ||
          raw['test_events'] is! int ||
          raw['test_events'] < 1 ||
          raw['policy_sha256'] is! String ||
          !RegExp(r'^[a-f0-9]{64}$').hasMatch(raw['policy_sha256']) ||
          !finite(raw['display_resolution_cm']) ||
          raw['display_resolution_cm'] <= 0 ||
          raw['display_resolution_cm'] > 100 ||
          data.points.any(
            (p) =>
                p.lowerDepthCm == null ||
                p.upperDepthCm == null ||
                !p.lowerDepthCm!.isFinite ||
                !p.upperDepthCm!.isFinite ||
                p.lowerDepthCm! < 0 ||
                p.upperDepthCm! > 1000 ||
                p.lowerDepthCm! > p.waterDepthCm! ||
                p.upperDepthCm! < p.waterDepthCm!,
          )) {
        throw const FormatException('Invalid calibrated uncertainty.');
      }
    }
    if (data.status == 'available' &&
        (publishedForecastFields.any((key) => json[key] == null) ||
            json['ingress_identity'] is! String ||
            (json['ingress_identity'] as String).isEmpty ||
            json['registry_version'] is! int ||
            (json['registry_version'] as int) < 1 ||
            json['timestamp_basis'] != 'device_measured' ||
            json['model_card_id'] != json['model_version'] ||
            data.source != 'model' ||
            json['forecast_id'] is! String ||
            !RegExp(
              r'^[a-f0-9-]{36}$',
            ).hasMatch(json['forecast_id'] as String) ||
            json['deployment_version'] is! int ||
            (json['deployment_version'] as int) < 1 ||
            json['reference_datum'] is! String ||
            (json['reference_datum'] as String).trim().isEmpty ||
            json['configuration_hash'] is! String ||
            !RegExp(
              r'^[a-f0-9]{64}$',
            ).hasMatch(json['configuration_hash'] as String) ||
            json['model_card_id'] is! String ||
            !RegExp(
              r'^[a-f0-9]{64}$',
            ).hasMatch(json['model_card_id'] as String) ||
            json['data_cutoff'] != json['input_last_recorded_at'] ||
            json['measurement_source'] != 'registry_verified_physical_device' ||
            data.points.any(
              (p) =>
                  p.targetAt !=
                  data.latestInputAt!.add(Duration(minutes: p.horizonMinutes)),
            ))) {
      throw const FormatException(
        'Published forecast identity or provenance is incomplete.',
      );
    }
    return data;
  }

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
          : value != null ||
                target != null ||
                row['lower_depth_cm'] != null ||
                row['upper_depth_cm'] != null) {
        throw const FormatException('Invalid forecast values.');
      }
      points.add(
        ForecastPoint(
          row['horizon_minutes'] as int,
          value,
          target,
          (row['lower_depth_cm'] as num?)?.toDouble(),
          (row['upper_depth_cm'] as num?)?.toDouble(),
        ),
      );
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
        'Synthetic response claimed a trained model.',
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
      publication: Map.unmodifiable({
        for (final key in [
          'forecast_id',
          'deployment_version',
          'configuration_hash',
          'reference_datum',
          'model_card_id',
          'data_cutoff',
          'measurement_source',
          'ingress_identity',
          'registry_version',
          'uncertainty',
        ])
          key: json[key],
      }),
    );
  }
}

String forecastDepth(double? value, [double resolution = 1]) => value == null
    ? '—'
    : '≈${((value / resolution.clamp(1, 100)).round() * resolution.clamp(1, 100)).toStringAsFixed(0)}';
String forecastInterval(ForecastPoint point) =>
    point.lowerDepthCm == null || point.upperDepthCm == null
    ? 'Uncertainty unavailable'
    : '${point.lowerDepthCm!.floor()}–${point.upperDepthCm!.ceil()} cm';

String predictionTime(DateTime? date) {
  if (date == null) return '—';
  final t = date.toLocal();
  String two(int n) => n.toString().padLeft(2, '0');
  return '${t.month}/${t.day} ${two(t.hour)}:${two(t.minute)}';
}
