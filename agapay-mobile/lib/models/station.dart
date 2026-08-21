import 'alert_tier.dart';
import 'trend_direction.dart';

/// Represents an IoT Flood Monitoring Sensor Station (ESP32 Station)
class Station {
  final String id;
  final String name;
  final String barangay;
  final double distanceKm;
  final double latitude;
  final double longitude;
  final double waterDepthCm;
  final double maxThresholdCm;
  final double advisoryThresholdCm;
  final double warningThresholdCm;
  final double evacuateThresholdCm;
  final double rainfallMm;
  final int batteryPercent;
  final bool isOnline;
  final DateTime lastUpdated;
  final TrendDirection trend;
  final int rssi; // Signal dBm, e.g. -68 dBm
  final bool solarCharging;
  final double flowSpeedMs;

  const Station({
    required this.id,
    required this.name,
    required this.barangay,
    required this.distanceKm,
    required this.latitude,
    required this.longitude,
    required this.waterDepthCm,
    this.maxThresholdCm = 100.0,
    this.advisoryThresholdCm = 40.0,
    this.warningThresholdCm = 70.0,
    this.evacuateThresholdCm = 85.0,
    required this.rainfallMm,
    required this.batteryPercent,
    this.isOnline = true,
    required this.lastUpdated,
    required this.trend,
    this.rssi = -65,
    this.solarCharging = true,
    this.flowSpeedMs = 0.8,
  });

  /// Computed water depth percentage (0.0 to 1.0)
  double get percentage {
    if (maxThresholdCm <= 0) return 0.0;
    return (waterDepthCm / maxThresholdCm).clamp(0.0, 1.0);
  }

  /// Evaluates alert tier based on current water depth
  AlertTier get alertTier {
    if (waterDepthCm >= evacuateThresholdCm) {
      return AlertTier.evacuate;
    } else if (waterDepthCm >= warningThresholdCm) {
      return AlertTier.warning;
    } else if (waterDepthCm >= advisoryThresholdCm) {
      return AlertTier.advisory;
    }
    return AlertTier.normal;
  }

  Station copyWith({
    String? id,
    String? name,
    String? barangay,
    double? distanceKm,
    double? latitude,
    double? longitude,
    double? waterDepthCm,
    double? maxThresholdCm,
    double? advisoryThresholdCm,
    double? warningThresholdCm,
    double? evacuateThresholdCm,
    double? rainfallMm,
    int? batteryPercent,
    bool? isOnline,
    DateTime? lastUpdated,
    TrendDirection? trend,
    int? rssi,
    bool? solarCharging,
    double? flowSpeedMs,
  }) {
    return Station(
      id: id ?? this.id,
      name: name ?? this.name,
      barangay: barangay ?? this.barangay,
      distanceKm: distanceKm ?? this.distanceKm,
      latitude: latitude ?? this.latitude,
      longitude: longitude ?? this.longitude,
      waterDepthCm: waterDepthCm ?? this.waterDepthCm,
      maxThresholdCm: maxThresholdCm ?? this.maxThresholdCm,
      advisoryThresholdCm: advisoryThresholdCm ?? this.advisoryThresholdCm,
      warningThresholdCm: warningThresholdCm ?? this.warningThresholdCm,
      evacuateThresholdCm: evacuateThresholdCm ?? this.evacuateThresholdCm,
      rainfallMm: rainfallMm ?? this.rainfallMm,
      batteryPercent: batteryPercent ?? this.batteryPercent,
      isOnline: isOnline ?? this.isOnline,
      lastUpdated: lastUpdated ?? this.lastUpdated,
      trend: trend ?? this.trend,
      rssi: rssi ?? this.rssi,
      solarCharging: solarCharging ?? this.solarCharging,
      flowSpeedMs: flowSpeedMs ?? this.flowSpeedMs,
    );
  }
}
