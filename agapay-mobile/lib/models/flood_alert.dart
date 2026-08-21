import 'alert_tier.dart';
import 'trend_direction.dart';

/// Flood Alert record with meteorological and threshold context
class FloodAlert {
  final String id;
  final AlertTier tier;
  final String title;
  final String description;
  final String stationId;
  final String stationName;
  final String barangay;
  final double waterLevelCm;
  final double thresholdCm;
  final TrendDirection trend;
  final double rainfallMm;
  final double predictedLevelCm;
  final String recommendedAction;
  final DateTime timestamp;
  final bool isAcknowledged;

  const FloodAlert({
    required this.id,
    required this.tier,
    required this.title,
    required this.description,
    required this.stationId,
    required this.stationName,
    required this.barangay,
    required this.waterLevelCm,
    required this.thresholdCm,
    required this.trend,
    required this.rainfallMm,
    required this.predictedLevelCm,
    required this.recommendedAction,
    required this.timestamp,
    this.isAcknowledged = false,
  });

  FloodAlert copyWith({
    String? id,
    AlertTier? tier,
    String? title,
    String? description,
    String? stationId,
    String? stationName,
    String? barangay,
    double? waterLevelCm,
    double? thresholdCm,
    TrendDirection? trend,
    double? rainfallMm,
    double? predictedLevelCm,
    String? recommendedAction,
    DateTime? timestamp,
    bool? isAcknowledged,
  }) {
    return FloodAlert(
      id: id ?? this.id,
      tier: tier ?? this.tier,
      title: title ?? this.title,
      description: description ?? this.description,
      stationId: stationId ?? this.stationId,
      stationName: stationName ?? this.stationName,
      barangay: barangay ?? this.barangay,
      waterLevelCm: waterLevelCm ?? this.waterLevelCm,
      thresholdCm: thresholdCm ?? this.thresholdCm,
      trend: trend ?? this.trend,
      rainfallMm: rainfallMm ?? this.rainfallMm,
      predictedLevelCm: predictedLevelCm ?? this.predictedLevelCm,
      recommendedAction: recommendedAction ?? this.recommendedAction,
      timestamp: timestamp ?? this.timestamp,
      isAcknowledged: isAcknowledged ?? this.isAcknowledged,
    );
  }
}
