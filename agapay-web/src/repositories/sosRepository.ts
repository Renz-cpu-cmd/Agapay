import { SOSBeacon } from '@/models/sos';
import { initialSOSBeacons } from '@/services/mockData';

export interface SOSRepository {
  getBeacons(): Promise<SOSBeacon[]>;
  acknowledgeSOS(id: string, responderTeam: string, officerName: string): Promise<SOSBeacon>;
  resolveSOS(id: string, officerName: string): Promise<SOSBeacon>;
}

export class MockSOSRepository implements SOSRepository {
  private beacons: SOSBeacon[] = [...initialSOSBeacons];

  async getBeacons(): Promise<SOSBeacon[]> {
    return [...this.beacons];
  }

  async acknowledgeSOS(id: string, responderTeam: string, officerName: string): Promise<SOSBeacon> {
    const idx = this.beacons.findIndex((b) => b.id === id);
    if (idx === -1) throw new Error('SOS Beacon not found');

    const updated: SOSBeacon = {
      ...this.beacons[idx],
      status: 'EnRoute',
      responderTeam: responderTeam || 'BDRRMC Quick Response Alpha',
      acknowledgedAt: new Date().toISOString(),
      acknowledgedBy: officerName,
    };
    this.beacons[idx] = updated;
    return updated;
  }

  async resolveSOS(id: string, officerName: string): Promise<SOSBeacon> {
    const idx = this.beacons.findIndex((b) => b.id === id);
    if (idx === -1) throw new Error('SOS Beacon not found');

    const updated: SOSBeacon = {
      ...this.beacons[idx],
      status: 'Resolved',
      resolvedAt: new Date().toISOString(),
      resolvedBy: officerName,
    };
    this.beacons[idx] = updated;
    return updated;
  }
}

export const sosRepository = new MockSOSRepository();
