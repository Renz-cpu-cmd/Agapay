import { FloodAlert } from '@/models/alert';
import { AlertLevel } from '@/constants/theme';
import { initialAlerts } from '@/services/mockData';

export interface AlertRepository {
  getAlerts(): Promise<FloodAlert[]>;
  resolveAlert(id: string, officerName: string): Promise<FloodAlert>;
  acknowledgeAlert(id: string): Promise<FloodAlert>;
  createManualAlert(params: {
    severity: AlertLevel;
    barangay: string;
    stationName: string;
    message: string;
    recommendedAction: string;
    broadcastBy: string;
  }): Promise<FloodAlert>;
}

export class MockAlertRepository implements AlertRepository {
  private alerts: FloodAlert[] = [...initialAlerts];

  async getAlerts(): Promise<FloodAlert[]> {
    return [...this.alerts];
  }

  async resolveAlert(id: string, officerName: string): Promise<FloodAlert> {
    const idx = this.alerts.findIndex((a) => a.id === id);
    if (idx === -1) throw new Error('Alert not found');

    const updated: FloodAlert = {
      ...this.alerts[idx],
      status: 'Resolved',
      resolvedAt: new Date().toISOString(),
      resolvedBy: officerName,
    };
    this.alerts[idx] = updated;
    return updated;
  }

  async acknowledgeAlert(id: string): Promise<FloodAlert> {
    const idx = this.alerts.findIndex((a) => a.id === id);
    if (idx === -1) throw new Error('Alert not found');

    const updated: FloodAlert = {
      ...this.alerts[idx],
      status: 'Acknowledged',
    };
    this.alerts[idx] = updated;
    return updated;
  }

  async createManualAlert(params: {
    severity: AlertLevel;
    barangay: string;
    stationName: string;
    message: string;
    recommendedAction: string;
    broadcastBy: string;
  }): Promise<FloodAlert> {
    const newAlert: FloodAlert = {
      id: `ALT-MANUAL-${Date.now().toString().slice(-4)}`,
      severity: params.severity,
      stationId: 'MANUAL_OVERRIDE',
      stationName: params.stationName,
      barangay: params.barangay,
      waterDepthCm: 95.0,
      thresholdCm: 90.0,
      rainfallMm: 20.0,
      trend: 'rising',
      message: params.message,
      recommendedAction: params.recommendedAction,
      createdAt: new Date().toISOString(),
      status: 'Active',
      isManualBroadcast: true,
      broadcastBy: params.broadcastBy,
    };
    this.alerts.unshift(newAlert);
    return newAlert;
  }
}

export const alertRepository = new MockAlertRepository();
