import { AlertLevel } from '@/constants/theme';
import { TrendDirection } from './station';

export type AlertStatus = 'Active' | 'Acknowledged' | 'Resolved';

export interface FloodAlert {
  id: string;
  severity: AlertLevel;
  stationId: string;
  stationName: string;
  barangay: string;
  waterDepthCm: number;
  thresholdCm: number;
  rainfallMm: number;
  trend: TrendDirection;
  message: string;
  recommendedAction: string;
  createdAt: string;
  status: AlertStatus;
  isManualBroadcast?: boolean;
  broadcastBy?: string;
  resolvedAt?: string;
  resolvedBy?: string;
}
