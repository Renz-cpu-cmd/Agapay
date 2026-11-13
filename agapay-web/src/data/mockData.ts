import type { StationChannels } from "../lib/channel-health";
import type { Measurement } from "../lib/measurements";

export type AlertTier = "EVACUATE" | "WARNING" | "ADVISORY" | "NORMAL" | "OFFLINE" | "UNKNOWN";

export interface Station {
  id: string;
  name: string;
  location: string;
  status: AlertTier;
  depth: Measurement;
  rain: Measurement;
  administrativeStatus?: "active"|"inactive"|"maintenance"|"unknown";
  lifecycle?:import("../lib/monitoring").MonitoringStation["lifecycle"];
  channelHealth?: StationChannels;
  configuration?: import("../lib/monitoring").MonitoringStation["configuration"];
  riseRate?: number|null;
  riseRateLower?: number|null;
  riseRateUpper?: number|null;
  trendReason?: string;
  trendCoverage?: number;
  trend: "rising_rapidly" | "rising" | "stable" | "falling" | "unknown";
  lastPing: string;
  firmware: string;
  sensorValid: boolean;
  isOnline: boolean;
  // "planned" exists only in the labelled demo fixtures below; operational stations use
  // the registry's "verified" / "unverified" state, or null when missing/invalid (R1).
  coordinates: { latitude: number; longitude: number; status: "planned" | "verified" | "unverified";
    precisionM?: number | null; basis?: "surveyed" | "owner_confirmed" | "estimated" | null } | null;
  coordinateStatus?: "verified" | "unverified" | "planned" | "missing" | "invalid";
  thresholds: { advisory: number; warning: number; evacuate: number };
  waterHistory: { time: string; level: number | null; recordedAt?: string; measuredAt?:string|null; receivedAt?:string|null }[];
  rainHistory?: { time: string; value: number | null; recordedAt?: string }[];
  barangay: string;
  dataSource?: "simulator" | "device" | "unverified" | "none" | "demo";
  sourceClass?: "physical_device" | "simulator" | "unverified";
  sourceTrusted?: boolean;
  depthSourceTrusted?: boolean;
  depthSourceId?: string|null;
  depthFresh?: boolean;
  depthStatus?: "fresh" | "retained" | "stale" | "missing";
  depthAgeSeconds?: number|null;
  heartbeatAgeSeconds?: number|null;
  measurementAge?: string;
  heartbeatAt?: string|null;
  hazardPolicyState?: "provisional" | "station_reviewed";
  hazardDecision?: string | null;
  observationTier?: AlertTier | null;
  hazardState?: "observed"|"unresolved"|"none"|"unknown";
  activeHazardTier?: Exclude<AlertTier,"OFFLINE"|"UNKNOWN">|null;
  connectionStatus?: "online" | "offline" | "no_data" | "inactive" | "maintenance" | "unconfirmed";
  observedAt?: string | null;
}

export interface Alert {
  id: string;
  stationId: string;
  stationName: string;
  tier: AlertTier;
  waterLevel: number | null;
  triggeredAt: string;
  resolvedAt?: string;
  status: "ACTIVE" | "RESOLVED";
  triggeredAgo: string;
  message?: string;
  reason?: string;
}

export interface SosBeacon {
  id: string;
  residentName: string;
  location: string;
  message: string;
  receivedAt: string;
  status: "ACTIVE" | "ACKNOWLEDGED" | "RESOLVED";
  acknowledgedBy?: string;
  acknowledgedAt?: string;
  lat: number;
  lng: number;
}

export interface User {
  id: string;
  name: string;
  email: string;
  role: "admin" | "officer" | "resident";
  barangay: string;
  status: "Active" | "Inactive";
  joinedAt: string;
}

function generateHistory(base: number, count = 24): { time: string; level: number }[] {
  const now = new Date(2026, 8, 1, 11, 46);
  return Array.from({ length: count }, (_, i) => {
    const t = new Date(now.getTime() - (count - 1 - i) * 30 * 60 * 1000);
    const hour = t.getHours().toString().padStart(2, "0");
    const min = t.getMinutes().toString().padStart(2, "0");
    const noise = (Math.sin(base * 10 + i * 7.3) * 0.5 + 0.2) * 6;
    const trend = (i / count) * (base - base * 0.35);
    return { time: `${hour}:${min}`, level: Math.max(0, Math.round((base * 0.35 + trend + noise) * 10) / 10) };
  });
}

const exerciseStations: (Omit<Station, "depth" | "rain"> & { waterLevel: number; rainfall: number })[] = [
  {
    id: "STATION_001",
    name: "UCU Irrigation Canal Station",
    location: "Irrigation canal in front of Urdaneta City University, San Vicente West",
    barangay: "San Vicente West",
    status: "EVACUATE",
    waterLevel: 103.2,
    rainfall: 8.2,
    trend: "rising_rapidly",
    lastPing: "2 sec ago",
    firmware: "v2.0.0",
    sensorValid: true,
    isOnline: true,
    // Planned point on the mapped channel across UCU's northern frontage.
    // Confirm the precise mounting position during the physical site survey.
    coordinates: { latitude: 15.98165, longitude: 120.560573, status: "planned" },
    thresholds: { advisory: 60, warning: 85, evacuate: 100 },
    waterHistory: generateHistory(103.2),
  },
  {
    id: "STATION_002",
    name: "Nancayasan Creek Station",
    location: "Nancayasan, Urdaneta City",
    barangay: "Nancayasan",
    status: "WARNING",
    waterLevel: 87.4,
    rainfall: 5.1,
    trend: "rising",
    lastPing: "6 sec ago",
    firmware: "v2.0.0",
    sensorValid: true,
    isOnline: true,
    coordinates: null,
    thresholds: { advisory: 55, warning: 80, evacuate: 95 },
    waterHistory: generateHistory(87.4),
  },
  {
    id: "STATION_003",
    name: "Poblacion Bridge Station",
    location: "Poblacion, Urdaneta City",
    barangay: "Poblacion",
    status: "ADVISORY",
    waterLevel: 64.1,
    rainfall: 2.8,
    trend: "rising",
    lastPing: "17 min ago",
    firmware: "v2.0.0",
    sensorValid: false,
    isOnline: false,
    coordinates: null,
    thresholds: { advisory: 60, warning: 80, evacuate: 100 },
    waterHistory: generateHistory(64.1),
  },
  {
    id: "STATION_004",
    name: "Bayaoas River Station",
    location: "Bayaoas, Urdaneta City",
    barangay: "Bayaoas",
    status: "NORMAL",
    waterLevel: 38.6,
    rainfall: 0.4,
    trend: "stable",
    lastPing: "4 sec ago",
    firmware: "v2.0.0",
    sensorValid: true,
    isOnline: true,
    coordinates: null,
    thresholds: { advisory: 65, warning: 85, evacuate: 100 },
    waterHistory: generateHistory(38.6),
  },
];

// Example fixtures are used only by the explicitly labeled demo workspace.
export const stations: Station[] = exerciseStations.map(({ waterLevel, rainfall, ...station }) => ({
  ...station,
  depth: { value: waterLevel, measuredAt: null, ageSeconds: null, state: "exercise", quality: "valid", latestSampleQuality: "valid", reason: "Example exercise depth" },
  rain: { value: rainfall, measuredAt: null, ageSeconds: null, state: "exercise", quality: "valid", latestSampleQuality: "valid", reason: "Example exercise rainfall" },
}));

export const alerts: Alert[] = [
  {
    id: "ALT-001",
    stationId: "STATION_001",
    stationName: "UCU Irrigation Canal Station",
    tier: "EVACUATE",
    waterLevel: 103.2,
    triggeredAt: "11:45 AM",
    status: "ACTIVE",
    triggeredAgo: "1 min ago",
  },
  {
    id: "ALT-002",
    stationId: "STATION_002",
    stationName: "Nancayasan Creek Station",
    tier: "WARNING",
    waterLevel: 87.4,
    triggeredAt: "11:39 AM",
    status: "ACTIVE",
    triggeredAgo: "7 min ago",
  },
  {
    id: "ALT-003",
    stationId: "STATION_003",
    stationName: "Poblacion Bridge Station",
    tier: "ADVISORY",
    waterLevel: 65.2,
    triggeredAt: "10:51 AM",
    resolvedAt: "11:22 AM",
    status: "RESOLVED",
    triggeredAgo: "55 min ago",
  },
  {
    id: "ALT-004",
    stationId: "STATION_004",
    stationName: "Bayaoas River Station",
    tier: "ADVISORY",
    waterLevel: 61.3,
    triggeredAt: "09:14 AM",
    resolvedAt: "10:05 AM",
    status: "RESOLVED",
    triggeredAgo: "2 hrs ago",
  },
];

export const sosBeacons: SosBeacon[] = [
  {
    id: "SOS-004",
    residentName: "Resident #004",
    location: "San Vicente, Urdaneta City",
    message: "Trapped on second floor, water rising fast",
    receivedAt: "11:47 AM",
    status: "ACTIVE",
    lat: 15.976,
    lng: 100.577,
  },
  {
    id: "SOS-003",
    residentName: "Resident #003",
    location: "Nancayasan, Urdaneta City",
    message: "Road flooded, cannot evacuate",
    receivedAt: "11:31 AM",
    status: "ACKNOWLEDGED",
    acknowledgedBy: "Officer Juan Dela Cruz",
    acknowledgedAt: "11:33 AM",
    lat: 15.98,
    lng: 100.571,
  },
  {
    id: "SOS-002",
    residentName: "Resident #002",
    location: "Poblacion, Urdaneta City",
    message: "Family stranded, need boat",
    receivedAt: "10:55 AM",
    status: "RESOLVED",
    acknowledgedBy: "Officer Maria Santos",
    acknowledgedAt: "10:57 AM",
    lat: 15.972,
    lng: 100.568,
  },
];

export const users: User[] = [
  {
    id: "USR-001",
    name: "Admin User",
    email: "admin@agapay.ph",
    role: "admin",
    barangay: "—",
    status: "Active",
    joinedAt: "Jan 10, 2026",
  },
  {
    id: "USR-002",
    name: "Juan Dela Cruz",
    email: "j.delacruz@urdaneta.gov.ph",
    role: "officer",
    barangay: "San Vicente",
    status: "Active",
    joinedAt: "Jan 12, 2026",
  },
  {
    id: "USR-003",
    name: "Maria Santos",
    email: "m.santos@urdaneta.gov.ph",
    role: "officer",
    barangay: "Nancayasan",
    status: "Active",
    joinedAt: "Jan 12, 2026",
  },
  {
    id: "USR-004",
    name: "Pedro Reyes",
    email: "pedro.reyes@gmail.com",
    role: "resident",
    barangay: "San Vicente",
    status: "Active",
    joinedAt: "Feb 2, 2026",
  },
  {
    id: "USR-005",
    name: "Ana Garcia",
    email: "ana.garcia@gmail.com",
    role: "resident",
    barangay: "Nancayasan",
    status: "Active",
    joinedAt: "Feb 8, 2026",
  },
  {
    id: "USR-006",
    name: "Roberto Lim",
    email: "r.lim@gmail.com",
    role: "resident",
    barangay: "Poblacion",
    status: "Inactive",
    joinedAt: "Mar 15, 2026",
  },
];

export const tierColor: Record<AlertTier, string> = {
  EVACUATE: "#ff0000",
  WARNING: "#f97316",
  ADVISORY: "#f5df00",
  NORMAL: "#00e83a",
  OFFLINE: "#6b7280",
  UNKNOWN: "#a855f7",
};

// Text uses semantic theme tokens; map markers and fills retain their raw colors.
export const tierTextColor: Record<AlertTier, string> = {
  EVACUATE: "var(--severity-evacuate-text, #ff0000)",
  WARNING: "var(--severity-warning-text, #f97316)",
  ADVISORY: "var(--severity-advisory-text, #f5df00)",
  NORMAL: "var(--severity-normal-text, #00e83a)",
  OFFLINE: "var(--severity-offline-text, #6b7280)",
  UNKNOWN: "var(--severity-unknown-text, #a855f7)",
};

export const tierBg: Record<AlertTier, string> = {
  EVACUATE: "rgba(239,68,68,0.12)",
  WARNING: "rgba(249,115,22,0.12)",
  ADVISORY: "rgba(234,179,8,0.12)",
  NORMAL: "rgba(34,197,94,0.1)",
  OFFLINE: "rgba(107,114,128,0.12)",
  UNKNOWN: "rgba(168,85,247,0.12)",
};

export const tierLabel: Record<AlertTier, string> = {
  EVACUATE: "EVACUATE",
  WARNING: "WARNING",
  ADVISORY: "ADVISORY",
  NORMAL: "NORMAL",
  OFFLINE: "OFFLINE",
  UNKNOWN: "NO DATA",
};

export const trendLabel: Record<string, string> = {
  unknown: "— Unknown trend",
  rising_rapidly: "↑ Rising Rapidly",
  rising: "↗ Rising",
  stable: "→ Stable",
  falling: "↘ Falling",
};
