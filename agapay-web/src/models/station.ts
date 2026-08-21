import { AlertLevel } from '@/constants/theme';

export type StationStatus = 'Online' | 'Offline' | 'Maintenance';
export type TrendDirection = 'rising' | 'stable' | 'falling';

export interface Station {
  id: string;
  name: string;
  barangay: string;
  latitude: number;
  longitude: number;
  waterDepthCm: number;
  maxThresholdCm: number;
  advisoryThresholdCm: number;
  warningThresholdCm: number;
  evacuateThresholdCm: number;
  rainfallMm: number;
  flowSpeedMs: number;
  batteryPercent: number;
  status: StationStatus;
  alertLevel: AlertLevel;
  trend: TrendDirection;
  lastPing: string;
  firmwareVersion: string;
  mqttConnected: boolean;
  rssi: number;
  solarCharging: boolean;
}

export function computeAlertLevel(station: Station): AlertLevel {
  if (station.waterDepthCm >= station.evacuateThresholdCm) return 'EVACUATE';
  if (station.waterDepthCm >= station.warningThresholdCm) return 'WARNING';
  if (station.waterDepthCm >= station.advisoryThresholdCm) return 'ADVISORY';
  return 'NORMAL';
}
