import 'alert_level.dart';

class MonitoringSample {
  MonitoringSample.fromJson(Map<String, dynamic> json)
    : sequenceNo = json['sequence_no'] as int,
      waterDepthCm = (json['water_depth_cm'] as num?)?.toDouble(),
      rainfallMm = (json['rainfall_mm'] as num?)?.toDouble(),
      sensorQuality = json['sensor_quality'] as String,
      recordedAt = DateTime.parse(json['recorded_at'] as String).toLocal();

  final int sequenceNo;
  final double? waterDepthCm;
  final double? rainfallMm;
  final String sensorQuality;
  final DateTime recordedAt;
}

class MonitoringStation {
  MonitoringStation.fromJson(Map<String, dynamic> json)
    : id = json['station_id'] as String,
      name = json['station_name'] as String,
      barangay = (json['barangay'] as String?) ?? 'Barangay unavailable',
      municipality =
          (json['municipality'] as String?) ?? 'Municipality unavailable',
      latitude = (json['latitude'] as num?)?.toDouble(),
      longitude = (json['longitude'] as num?)?.toDouble(),
      coordinateStatus = json['coordinate_status'] as String?,
      coordinatePrecisionM = (json['coordinate_precision_m'] as num?)?.toInt(),
      coordinateBasis = json['coordinate_basis'] as String?,
      connectionStatus = json['connection_status'] as String,
      isOnline = json['is_online'] as bool,
      isStale = json['is_stale'] as bool,
      ageSeconds = json['depth_age_seconds'] as int?,
      heartbeatAgeSeconds = json['heartbeat_age_seconds'] as int?,
      depthAgeSeconds = json['depth_age_seconds'] as int?,
      depthFresh = json['depth_fresh'] == true,
      heartbeatFresh = json['heartbeat_fresh'] == true,
      depthStatus = (json['depth_status'] as String?) ?? 'missing',
      heartbeatAt = _time(json['heartbeat_at']),
      latestSampleAt = _time(json['latest_sample_at']),
      lastValidDepthAt = _time(json['last_valid_depth_at']),
      hazardReviewRequired = json["hazard_review_required"] == true,
      hazardDecision = json["hazard_decision"] as String?,
      hazardPolicyState =
          json["hazard_policy_state"] as String? ?? "provisional",
      observationTier = json["observation_tier"] as String?,
      hazardState = (json['hazard_state'] as String?) ?? 'unknown',
      activeHazardTier = json['active_hazard_tier'] as String?,
      alertLevel = _alert(json['alert_tier'] as String?),
      trend = json['trend'] as String? ?? 'unknown',
      riseRate = (json['rise_rate_cm_per_minute'] as num?)?.toDouble(),
      riseRateLower = (json['rise_rate_lower'] as num?)?.toDouble(),
      riseRateUpper = (json['rise_rate_upper'] as num?)?.toDouble(),
      trendCoverage = (json['trend_coverage'] as num?)?.toDouble(),
      trendReason =
          json['trend_reason'] as String? ??
          'Insufficient measurement timing/coverage',
      trendWindowStart = _time(json['trend_window_start']),
      trendWindowEnd = _time(json['trend_window_end']),
      currentDepthCm = (json['current_depth_cm'] as num?)?.toDouble(),
      latestDepthCm = (json['latest_depth_cm'] as num?)?.toDouble(),
      latestRainfallMm =
          ((json['rainfall_product'] as Map?)?['rainfall_mm'] as num?)
              ?.toDouble(),
      rainfallProduct = _immutableMap(json['rainfall_product']),
      rainfallFresh = json['rainfall_fresh'] == true,
      rainfallAgeSeconds = json['rainfall_age_seconds'] as int?,
      configuration = _immutableMap(json['configuration']),
      channelHealth = _immutableMap(json['channel_health']),
      lifecycle = _immutableMap(json['lifecycle']),
      sensorQuality = json['sensor_quality'] as String?,
      observedAt = _time(json['last_valid_depth_at']),
      firmwareVersion = json['firmware_version'] as String?,
      source = json['source'] as String,
      sourceClass = (json['source_class'] as String?) ?? 'unverified',
      sourceTrusted = json['source_trusted'] == true,
      depthSourceTrusted = json['depth_source_trusted'] == true,
      stream = (json['stream'] as String?) ?? 'unverified',
      thresholdAdvisoryCm = (json['threshold_advisory_cm'] as num).toDouble(),
      thresholdWarningCm = (json['threshold_warning_cm'] as num).toDouble(),
      thresholdEvacuateCm = (json['threshold_evacuate_cm'] as num).toDouble(),
      history = List.unmodifiable(
        (json['history'] as List<dynamic>)
            .map(
              (value) =>
                  MonitoringSample.fromJson(value as Map<String, dynamic>),
            )
            .toList(growable: false),
      );

  final Map<String, dynamic>? rainfallProduct,
      configuration,
      lifecycle,
      channelHealth;
  final bool rainfallFresh;
  final int? rainfallAgeSeconds;
  /// A7.1: recorded radius (m) of the registry position and how it was obtained
  /// ('surveyed' | 'owner_confirmed' | 'estimated'). Null = never recorded: the
  /// existing presentation is kept and nothing is inferred from the digits.
  final int? coordinatePrecisionM;
  final String? coordinateBasis;
  final String connectionStatus, trend, source;
  final double? riseRate, riseRateLower, riseRateUpper, trendCoverage;
  final String trendReason;
  final DateTime? trendWindowStart, trendWindowEnd;
  final bool isOnline, isStale;
  final int? ageSeconds;
  final int? heartbeatAgeSeconds, depthAgeSeconds;
  final bool depthFresh, heartbeatFresh, sourceTrusted, depthSourceTrusted;
  final bool hazardReviewRequired;
  final String? hazardDecision, observationTier;
  final String hazardPolicyState;
  final String depthStatus, hazardState, sourceClass, stream;
  final String? activeHazardTier;
  final DateTime? heartbeatAt, latestSampleAt, lastValidDepthAt;
  final AlertLevel? alertLevel;
  final double? currentDepthCm, latestDepthCm, latestRainfallMm;
  final String? sensorQuality, firmwareVersion;
  final DateTime? observedAt;
  final double thresholdAdvisoryCm, thresholdWarningCm, thresholdEvacuateCm;
  final List<MonitoringSample> history;

  bool get isSimulator => source == 'simulator';
  /// Device authentication identifies the source. It is not sensor calibration,
  /// installation validation or warning authority (A7.1).
  String get sourceLabel => sourceClass == 'physical_device' && sourceTrusted
      ? 'Authenticated registered device'
      : sourceClass == 'simulator'
      ? 'Synthetic source'
      : 'Unverified source';
  bool get hasValidReading => currentDepthCm != null;

  /// R1: registry position, or null. A missing, half-missing, non-finite or
  /// out-of-range pair is never mapped; zero is a valid coordinate. Nothing is
  /// ever substituted for a missing position.
  ({double latitude, double longitude})? get mapCoordinates {
    final lat = latitude, lon = longitude;
    if (lat == null || lon == null || coordinateStatus == 'missing' ||
        coordinateStatus == 'invalid' || !lat.isFinite || !lon.isFinite ||
        lat.abs() > 90 || lon.abs() > 180) {
      return null;
    }
    return (latitude: lat, longitude: lon);
  }

  /// 'verified' | 'unverified' | 'missing' | 'invalid'. An older server without
  /// the field fails closed to 'unverified' for a valid pair.
  String get locationState => mapCoordinates != null
      ? (coordinateStatus == 'verified' ? 'verified' : 'unverified')
      : coordinateStatus == 'invalid'
      ? 'invalid' // the server nulls an invalid stored pair
      : (latitude == null && longitude == null) || coordinateStatus == 'missing'
      ? 'missing'
      : 'invalid';

  /// Radius at or below which a surveyed pair may be shown as an exact point.
  static const precisePointRadiusM = 50;

  /// True only when recorded metadata says the pin is an area, not a point.
  bool get locationApproximate =>
      mapCoordinates != null &&
      coordinatePrecisionM != null &&
      (coordinateBasis != 'surveyed' ||
          coordinatePrecisionM! > precisePointRadiusM);

  static String _radius(int metres) => metres >= 1000
      ? '~${(metres / 1000).round()} km'
      : '~$metres m';

  static String _basis(String? basis) => switch (basis) {
    'owner_confirmed' => 'owner-confirmed',
    'surveyed' => 'surveyed',
    _ => 'estimated',
  };

  /// Location wording for the map card. Precise or unrecorded precision keeps the
  /// existing registry wording; missing/invalid pairs never get a pin (R1).
  String get locationLabel {
    final state = locationState;
    if (state != 'verified' && state != 'unverified') {
      return state == 'missing'
          ? 'Coordinates unavailable · no map pin'
          : 'Recorded location invalid · no map pin';
    }
    if (locationApproximate) {
      final detail =
          '${_radius(coordinatePrecisionM!)}, ${_basis(coordinateBasis)}';
      return state == 'verified'
          ? 'Approximate location ($detail)'
          : 'Approximate unconfirmed location ($detail)';
    }
    if (state == 'unverified') return 'Unconfirmed registry location';
    return coordinateBasis == 'surveyed' && coordinatePrecisionM != null
        ? 'Confirmed registry location (±$coordinatePrecisionM m, surveyed)'
        : 'Confirmed registry location';
  }

  AlertLevel get observationLevel =>
      _alert(observationTier) ?? AlertLevel.unknown;

  /// R4, fail-closed: an observed tier may be presented as an operational warning
  /// only for a registry-verified physical source whose applied configuration
  /// matches an internally field_reviewed revision on an active station. Missing
  /// fields (older servers, fixtures) are unverified. Not LGU authorization.
  bool get operationallyVerified =>
      depthSourceTrusted &&
      configuration?['validation_status'] == 'field_reviewed' &&
      configuration?['status'] == 'matched' &&
      lifecycle?['state'] == 'active';

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
    : serviceHealth = _immutableMap(json['service_health']),
      checkedAt = DateTime.parse(json['checked_at'] as String).toLocal(),
      staleAfterSeconds = json['stale_after_seconds'] as int,
      stations = List.unmodifiable(
        (json['stations'] as List<dynamic>)
            .map(
              (value) =>
                  MonitoringStation.fromJson(value as Map<String, dynamic>),
            )
            .toList(growable: false),
      );

  final DateTime checkedAt;
  final int staleAfterSeconds;
  final List<MonitoringStation> stations;
  final Map<String, dynamic>? serviceHealth;
}

Map<String, dynamic>? _immutableMap(dynamic value) => value is Map
    ? Map.unmodifiable(value.map((k, v) => MapEntry(k.toString(), _freeze(v))))
    : null;
dynamic _freeze(dynamic value) => value is Map
    ? _immutableMap(value)
    : value is List
    ? List.unmodifiable(value.map(_freeze))
    : value;

/// One immutable interpretation at a single instant; no screen-owned timestamps.
class ChannelFreshness {
  const ChannelFreshness({
    required this.value,
    required this.measuredAt,
    required this.ageSeconds,
    required this.status,
    required this.quality,
    required this.source,
    required this.fresh,
  });
  final double? value;
  final DateTime? measuredAt;
  final int? ageSeconds;
  final String status, quality, source;
  final bool fresh;
}

class StationFreshnessView {
  const StationFreshnessView({
    required this.station,
    required this.asOf,
    required this.depth,
    required this.rain,
    required this.heartbeat,
    required this.sourceLabel,
    required this.sourceStatus,
    required this.hazardState,
  });
  final MonitoringStation station;
  final DateTime asOf;
  final ChannelFreshness depth, rain, heartbeat;
  final String sourceLabel, sourceStatus, hazardState;
}
