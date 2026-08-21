export interface TelemetryPoint {
  timestamp: string;
  waterDepthCm: number;
  rainfallMm: number;
  flowSpeedMs: number;
  batteryPercent: number;
  isPrediction?: boolean;
  predictionLabel?: string;
}

export interface PredictionPoint {
  timeLabel: string; // T+30 min, T+60 min, T+90 min
  predictedDepthCm: number;
  confidenceInterval: [number, number];
  rainfallEstimatedMm: number;
}
