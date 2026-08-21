export type SOSStatus = 'Active' | 'Acknowledged' | 'EnRoute' | 'Resolved';

export interface SOSBeacon {
  id: string;
  residentName: string;
  phone: string;
  barangay: string;
  latitude: number;
  longitude: number;
  message: string;
  createdAt: string;
  status: SOSStatus;
  responderTeam?: string;
  acknowledgedAt?: string;
  acknowledgedBy?: string;
  resolvedAt?: string;
  resolvedBy?: string;
  assignedVehicle?: string;
}
