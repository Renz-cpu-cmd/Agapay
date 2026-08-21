import { Station, computeAlertLevel } from '@/models/station';
import { TelemetryPoint, PredictionPoint } from '@/models/telemetry';
import { initialStations, generateTelemetryHistory, generateMLPredictions } from '@/services/mockData';

export interface StationRepository {
  getStations(): Promise<Station[]>;
  getStationById(id: string): Promise<Station | undefined>;
  getTelemetryHistory(stationId: string, hours: number): Promise<TelemetryPoint[]>;
  getMLPredictions(stationId: string): Promise<PredictionPoint[]>;
  updateStationThresholds(
    stationId: string,
    thresholds: { advisory: number; warning: number; evacuate: number }
  ): Promise<Station>;
}

export class MockStationRepository implements StationRepository {
  private stations: Station[] = [...initialStations];

  async getStations(): Promise<Station[]> {
    return [...this.stations];
  }

  async getStationById(id: string): Promise<Station | undefined> {
    return this.stations.find((s) => s.id === id);
  }

  async getTelemetryHistory(stationId: string, hours: number): Promise<TelemetryPoint[]> {
    return generateTelemetryHistory(stationId, hours);
  }

  async getMLPredictions(stationId: string): Promise<PredictionPoint[]> {
    return generateMLPredictions(stationId);
  }

  async updateStationThresholds(
    stationId: string,
    thresholds: { advisory: number; warning: number; evacuate: number }
  ): Promise<Station> {
    const index = this.stations.findIndex((s) => s.id === stationId);
    if (index === -1) throw new Error('Station not found');

    const updated: Station = {
      ...this.stations[index],
      advisoryThresholdCm: thresholds.advisory,
      warningThresholdCm: thresholds.warning,
      evacuateThresholdCm: thresholds.evacuate,
    };
    updated.alertLevel = computeAlertLevel(updated);
    this.stations[index] = updated;
    return updated;
  }
}

export const stationRepository = new MockStationRepository();
