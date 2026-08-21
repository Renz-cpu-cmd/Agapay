/// Historical or Predicted Telemetry Data Point
class TelemetryDataPoint {
  final DateTime timestamp;
  final double waterDepthCm;
  final double rainfallMm;
  final bool isPredicted;
  final String? predictionLabel; // e.g. "T+30 min"

  const TelemetryDataPoint({
    required this.timestamp,
    required this.waterDepthCm,
    required this.rainfallMm,
    this.isPredicted = false,
    this.predictionLabel,
  });
}

/// Aggregated summary statistics for a timeframe
class TelemetrySummary {
  final double minDepthCm;
  final double maxDepthCm;
  final double avgDepthCm;
  final double currentDepthCm;
  final double totalRainfallMm;
  final List<TelemetryDataPoint> history;
  final List<TelemetryDataPoint> predictions;

  const TelemetrySummary({
    required this.minDepthCm,
    required this.maxDepthCm,
    required this.avgDepthCm,
    required this.currentDepthCm,
    required this.totalRainfallMm,
    required this.history,
    required this.predictions,
  });
}
