import type { AlertTier } from "@/data/mockData";

export type MonitoringSample = {
  sequence_no: number;
  water_depth_cm: number | null;
  rainfall_mm: number;
  sensor_quality: "valid" | "invalid";
  device_uptime_ms: number;
  recorded_at: string;
};

export type MonitoringStation = {
  station_id: string;
  station_name: string;
  barangay: string | null;
  municipality: string | null;
  latitude: number | null;
  longitude: number | null;
  administrative_status: "active" | "inactive" | "maintenance";
  connection_status: "online" | "offline" | "no_data" | "inactive" | "maintenance";
  is_online: boolean;
  is_stale: boolean;
  age_seconds: number | null;
  alert_tier: Exclude<AlertTier, "OFFLINE" | "UNKNOWN"> | null;
  trend: "rising_rapidly" | "rising" | "stable" | "falling";
  current_depth_cm: number | null;
  latest_depth_cm: number | null;
  latest_rainfall_mm: number | null;
  sensor_quality: "valid" | "invalid" | null;
  last_ping: string | null;
  observed_at: string | null;
  firmware_version: string | null;
  source: "simulator" | "device" | "none";
  threshold_advisory_cm: number;
  threshold_warning_cm: number;
  threshold_evacuate_cm: number;
  history: MonitoringSample[];
};

export type MonitoringSnapshot = {
  checked_at: string;
  stale_after_seconds: number;
  stations: MonitoringStation[];
};

export function ageLabel(seconds: number | null, connection: MonitoringStation["connection_status"]) {
  if (seconds === null) return connection === "no_data" ? "No readings yet" : "Unknown";
  if (seconds < 60) return `${seconds} sec ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  return `${hours} hr${hours === 1 ? "" : "s"} ago`;
}
