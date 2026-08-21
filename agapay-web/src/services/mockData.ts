import { Station } from '@/models/station';
import { FloodAlert } from '@/models/alert';
import { SOSBeacon } from '@/models/sos';
import { User } from '@/models/user';
import { TelemetryPoint, PredictionPoint } from '@/models/telemetry';

export const initialStations: Station[] = [
  {
    id: 'STATION_001',
    name: 'Brgy. San Nicolas River Bridge',
    barangay: 'Brgy. San Nicolas',
    latitude: 14.7365,
    longitude: 120.9582,
    waterDepthCm: 102.4,
    maxThresholdCm: 120.0,
    advisoryThresholdCm: 45.0,
    warningThresholdCm: 75.0,
    evacuateThresholdCm: 90.0,
    rainfallMm: 18.5,
    flowSpeedMs: 2.1,
    batteryPercent: 84,
    status: 'Online',
    alertLevel: 'EVACUATE',
    trend: 'rising',
    lastPing: new Date(Date.now() - 1000 * 15).toISOString(),
    firmwareVersion: 'v2.4.1-esp32',
    mqttConnected: true,
    rssi: -58,
    solarCharging: true,
  },
  {
    id: 'STATION_002',
    name: 'Brgy. Poblacion River Station',
    barangay: 'Brgy. Poblacion',
    latitude: 14.7410,
    longitude: 120.9630,
    waterDepthCm: 87.2,
    maxThresholdCm: 120.0,
    advisoryThresholdCm: 45.0,
    warningThresholdCm: 75.0,
    evacuateThresholdCm: 90.0,
    rainfallMm: 14.2,
    flowSpeedMs: 1.75,
    batteryPercent: 91,
    status: 'Online',
    alertLevel: 'WARNING',
    trend: 'rising',
    lastPing: new Date(Date.now() - 1000 * 30).toISOString(),
    firmwareVersion: 'v2.4.1-esp32',
    mqttConnected: true,
    rssi: -62,
    solarCharging: true,
  },
  {
    id: 'STATION_003',
    name: 'Brgy. San Vicente Monitoring Station',
    barangay: 'Brgy. San Vicente',
    latitude: 14.7290,
    longitude: 120.9490,
    waterDepthCm: 48.0,
    maxThresholdCm: 120.0,
    advisoryThresholdCm: 45.0,
    warningThresholdCm: 75.0,
    evacuateThresholdCm: 90.0,
    rainfallMm: 5.4,
    flowSpeedMs: 0.82,
    batteryPercent: 96,
    status: 'Online',
    alertLevel: 'ADVISORY',
    trend: 'stable',
    lastPing: new Date(Date.now() - 1000 * 45).toISOString(),
    firmwareVersion: 'v2.3.8-esp32',
    mqttConnected: true,
    rssi: -68,
    solarCharging: false,
  },
  {
    id: 'STATION_004',
    name: 'Brgy. Santa Cruz River Sensor',
    barangay: 'Brgy. Santa Cruz',
    latitude: 14.7480,
    longitude: 120.9700,
    waterDepthCm: 28.5,
    maxThresholdCm: 120.0,
    advisoryThresholdCm: 45.0,
    warningThresholdCm: 75.0,
    evacuateThresholdCm: 90.0,
    rainfallMm: 1.2,
    flowSpeedMs: 0.45,
    batteryPercent: 98,
    status: 'Online',
    alertLevel: 'NORMAL',
    trend: 'falling',
    lastPing: new Date(Date.now() - 1000 * 60).toISOString(),
    firmwareVersion: 'v2.4.1-esp32',
    mqttConnected: true,
    rssi: -54,
    solarCharging: true,
  },
  {
    id: 'STATION_005',
    name: 'Brgy. Santo Rosario Basin Point',
    barangay: 'Brgy. Santo Rosario',
    latitude: 14.7220,
    longitude: 120.9420,
    waterDepthCm: 32.0,
    maxThresholdCm: 120.0,
    advisoryThresholdCm: 45.0,
    warningThresholdCm: 75.0,
    evacuateThresholdCm: 90.0,
    rainfallMm: 0.8,
    flowSpeedMs: 0.35,
    batteryPercent: 67,
    status: 'Maintenance',
    alertLevel: 'NORMAL',
    trend: 'stable',
    lastPing: new Date(Date.now() - 1000 * 180).toISOString(),
    firmwareVersion: 'v2.2.0-esp32',
    mqttConnected: false,
    rssi: -82,
    solarCharging: false,
  },
];

export const initialAlerts: FloodAlert[] = [
  {
    id: 'ALT-2026-001',
    severity: 'EVACUATE',
    stationId: 'STATION_001',
    stationName: 'Brgy. San Nicolas River Bridge',
    barangay: 'Brgy. San Nicolas',
    waterDepthCm: 102.4,
    thresholdCm: 90.0,
    rainfallMm: 18.5,
    trend: 'rising',
    message: 'Water level reached critical 102.4 cm (exceeded 90 cm evacuation limit). River overflow imminent.',
    recommendedAction: 'Immediate mandatory evacuation to San Nicolas Elementary School Shelter.',
    createdAt: new Date(Date.now() - 1000 * 60 * 2).toISOString(),
    status: 'Active',
  },
  {
    id: 'ALT-2026-002',
    severity: 'WARNING',
    stationId: 'STATION_002',
    stationName: 'Brgy. Poblacion River Station',
    barangay: 'Brgy. Poblacion',
    waterDepthCm: 87.2,
    thresholdCm: 75.0,
    rainfallMm: 14.2,
    trend: 'rising',
    message: 'Water level reached 87.2 cm warning threshold due to upstream runoff.',
    recommendedAction: 'Deploy rescue boats on standby. Advise ground floor residents to secure belongings.',
    createdAt: new Date(Date.now() - 1000 * 60 * 5).toISOString(),
    status: 'Active',
  },
  {
    id: 'ALT-2026-003',
    severity: 'ADVISORY',
    stationId: 'STATION_003',
    stationName: 'Brgy. San Vicente Monitoring Station',
    barangay: 'Brgy. San Vicente',
    waterDepthCm: 48.0,
    thresholdCm: 45.0,
    rainfallMm: 5.4,
    trend: 'stable',
    message: 'Water depth crossed 45.0 cm advisory limit. Current inflow stable.',
    recommendedAction: 'Monitor hourly hydrographs and inspect river drainage gates.',
    createdAt: new Date(Date.now() - 1000 * 60 * 20).toISOString(),
    status: 'Acknowledged',
  },
];

export const initialSOSBeacons: SOSBeacon[] = [
  {
    id: 'SOS-8801',
    residentName: 'Juan Dela Cruz',
    phone: '+63 917 555 0192',
    barangay: 'Brgy. San Nicolas',
    latitude: 14.7358,
    longitude: 120.9575,
    message: 'Trapped on 2nd floor roof with 2 elderly family members. Floodwaters at ground floor ceiling.',
    createdAt: new Date(Date.now() - 1000 * 60 * 8).toISOString(),
    status: 'Active',
  },
  {
    id: 'SOS-8802',
    residentName: 'Elena Soriano',
    phone: '+63 918 444 8921',
    barangay: 'Brgy. Poblacion',
    latitude: 14.7415,
    longitude: 120.9622,
    message: 'Medical oxygen patient stranded at 14 Mabini St. Water level 1.2m outside house.',
    createdAt: new Date(Date.now() - 1000 * 60 * 18).toISOString(),
    status: 'EnRoute',
    responderTeam: 'BDRRMC Rescue Alpha',
    assignedVehicle: 'Inflatable Boat #2',
    acknowledgedAt: new Date(Date.now() - 1000 * 60 * 14).toISOString(),
    acknowledgedBy: 'Capt. R. Mendoza',
  },
  {
    id: 'SOS-8803',
    residentName: 'Roberto Gomez',
    phone: '+63 920 333 1187',
    barangay: 'Brgy. San Nicolas',
    latitude: 14.7370,
    longitude: 120.9590,
    message: 'Vehicle stalled in fast-moving water near San Nicolas Bridge approach.',
    createdAt: new Date(Date.now() - 1000 * 60 * 35).toISOString(),
    status: 'Acknowledged',
    responderTeam: 'Station 1 Response Unit',
    acknowledgedAt: new Date(Date.now() - 1000 * 60 * 30).toISOString(),
    acknowledgedBy: 'Officer T. Santos',
  },
];

export const initialUsers: User[] = [
  {
    id: 'USR-001',
    name: 'Cmdr. Antonio Ramos',
    email: 'antonio.ramos@lgu.drrmc.gov.ph',
    role: 'Admin',
    barangay: 'Central DRRM Command',
    phone: '+63 917 888 1001',
    status: 'Active',
    createdAt: '2025-01-15',
    lastLogin: '2026-08-21 23:45',
    badgeNumber: 'LGU-DRRM-001',
  },
  {
    id: 'USR-002',
    name: 'Officer Teresa Santos',
    email: 'teresa.santos@lgu.drrmc.gov.ph',
    role: 'Officer',
    barangay: 'Brgy. San Nicolas',
    phone: '+63 917 888 1002',
    status: 'Active',
    createdAt: '2025-03-10',
    lastLogin: '2026-08-21 23:50',
    badgeNumber: 'LGU-DRRM-044',
  },
  {
    id: 'USR-003',
    name: 'Capt. Rodolfo Mendoza',
    email: 'rodolfo.mendoza@rescue.gov.ph',
    role: 'Responder',
    barangay: 'Brgy. Poblacion',
    phone: '+63 918 999 2201',
    status: 'Active',
    createdAt: '2025-06-01',
    lastLogin: '2026-08-21 22:15',
    badgeNumber: 'RESCUE-BOAT-01',
  },
  {
    id: 'USR-004',
    name: 'Officer Manuel Reyes',
    email: 'manuel.reyes@lgu.drrmc.gov.ph',
    role: 'Officer',
    barangay: 'Brgy. San Vicente',
    phone: '+63 919 777 3302',
    status: 'Inactive',
    createdAt: '2025-08-20',
    lastLogin: '2026-08-19 14:30',
    badgeNumber: 'LGU-DRRM-059',
  },
];

export function generateTelemetryHistory(stationId: string, hours: number): TelemetryPoint[] {
  const points: TelemetryPoint[] = [];
  const now = Date.now();
  const station = initialStations.find((s) => s.id === stationId) || initialStations[0];
  const baseDepth = station.waterDepthCm;
  const count = hours === 24 ? 24 : hours === 168 ? 28 : 30;
  const intervalMs = (hours * 3600 * 1000) / count;

  for (let i = count; i >= 0; i--) {
    const time = new Date(now - i * intervalMs);
    const wave = Math.sin(i * 0.4) * 8.0;
    const depth = Math.max(10, baseDepth - i * 1.5 + wave);
    const rain = Math.max(0, station.rainfallMm - (i % 6) * 1.8);

    points.push({
      timestamp: time.toISOString(),
      waterDepthCm: parseFloat(depth.toFixed(1)),
      rainfallMm: parseFloat(rain.toFixed(1)),
      flowSpeedMs: parseFloat(Math.max(0.2, station.flowSpeedMs - i * 0.03).toFixed(2)),
      batteryPercent: Math.min(100, Math.max(70, station.batteryPercent - (i % 3))),
    });
  }

  return points;
}

export function generateMLPredictions(stationId: string): PredictionPoint[] {
  const station = initialStations.find((s) => s.id === stationId) || initialStations[0];
  const base = station.waterDepthCm;

  return [
    {
      timeLabel: 'T+30 min',
      predictedDepthCm: parseFloat((base + 6.2).toFixed(1)),
      confidenceInterval: [parseFloat((base + 4.5).toFixed(1)), parseFloat((base + 8.0).toFixed(1))],
      rainfallEstimatedMm: parseFloat((station.rainfallMm * 1.05).toFixed(1)),
    },
    {
      timeLabel: 'T+60 min',
      predictedDepthCm: parseFloat((base + 12.8).toFixed(1)),
      confidenceInterval: [parseFloat((base + 9.2).toFixed(1)), parseFloat((base + 16.5).toFixed(1))],
      rainfallEstimatedMm: parseFloat((station.rainfallMm * 1.15).toFixed(1)),
    },
    {
      timeLabel: 'T+90 min',
      predictedDepthCm: parseFloat((base + 19.5).toFixed(1)),
      confidenceInterval: [parseFloat((base + 14.0).toFixed(1)), parseFloat((base + 25.0).toFixed(1))],
      rainfallEstimatedMm: parseFloat((station.rainfallMm * 1.25).toFixed(1)),
    },
  ];
}
