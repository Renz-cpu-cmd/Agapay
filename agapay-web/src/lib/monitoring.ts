import { ageChannels, type StationChannels } from "./channel-health";
import type { AlertTier } from "@/data/mockData";

export type MonitoringSample = {
  sequence_no: number;
  water_depth_cm: number | null;
  rainfall_mm: number|null;
  sensor_quality: "valid" | "invalid";
  device_uptime_ms: number;
  recorded_at: string;
  measured_at?: string|null;
  received_at?: string|null;
};

export type MonitoringStation = {
  station_id: string;
  station_name: string;
  barangay: string | null;
  municipality: string | null;
  latitude: number | null;
  longitude: number | null;
  /** R1 registry location state. Absent (older server) is treated as unverified at best. */
  coordinate_status?: "verified" | "unverified" | "missing" | "invalid";
  /** A7.1 recorded radius (m) of the registry position and how it was obtained; null = not recorded. */
  coordinate_precision_m?: number | null;
  coordinate_basis?: "surveyed" | "owner_confirmed" | "estimated" | null;
  administrative_status: "active" | "inactive" | "maintenance";
  connection_status: "online" | "offline" | "no_data" | "inactive" | "maintenance";
  /** Client evidence flag; an API failure does not establish a device outage. */
  connection_unconfirmed?: boolean;
  is_online: boolean;
  is_stale: boolean;
  age_seconds: number | null;
  heartbeat_at: string | null;
  heartbeat_age_seconds: number | null;
  heartbeat_fresh: boolean;
  latest_sample_at: string | null;
  latest_sample_age_seconds: number | null;
  last_valid_depth_at: string | null;
  depth_age_seconds: number | null;
  depth_fresh: boolean;
  depth_status: "fresh" | "retained" | "stale" | "missing";
  rainfall_observed_at: string | null;
  rainfall_age_seconds: number | null;
  rainfall_fresh: boolean;
  hazard_state: "observed" | "unresolved" | "none" | "unknown";
  active_hazard_tier: MonitoringStation["alert_tier"];
  active_alert_id: number | null;
  observation_tier?: Exclude<AlertTier, "OFFLINE" | "UNKNOWN"> | null;
  hazard_policy_state?: "provisional" | "station_reviewed";
  hazard_decision?: string | null;
  hazard_review_required?: boolean;
  alert_tier: Exclude<AlertTier, "OFFLINE" | "UNKNOWN"> | null;
  lifecycle?:{state:string;revision:number;hazard_policy:string;external_sensor_notifications:boolean;local_alarm_policy:string};
  channel_health?: StationChannels|null;
  rainfall_product?: {product:string;rainfall_mm:number|null;tip_count:number|null;interval_start:string|null;interval_end:string|null;quality:string;source:string;coverage:string;coverage_complete:boolean;calibration_version:string|null;mm_per_tip:number|null};
  configuration?: {status:string;config_hash?:string;applied_config_hash?:string|null;revision?:number;validation_status:string;local_alert_profile?:string;sensor_fault?:string;installation?:{installation_height_cm:number;rain_mm_per_tip:number}};
  rise_rate_cm_per_minute?: number|null;
  rise_rate_lower?: number|null;
  rise_rate_upper?: number|null;
  /** Migration 0010: staff-only operator-phone GPS fix for a portable station; never the registry position. */
  live_position?: {latitude:number;longitude:number;accuracy_m:number;captured_at:string;age_seconds:number;fresh:boolean;tracking_active:boolean;source:"operator_phone_gps"}|null;
  trend_window_start?: string|null;
  trend_window_end?: string|null;
  trend_sample_count?: number;
  trend_bin_count?: number;
  trend_coverage?: number;
  trend_reason?: string;
  trend_method?: string;
  trend: "rising_rapidly" | "rising" | "stable" | "falling" | "unknown";
  current_depth_cm: number | null;
  latest_depth_cm: number | null;
  latest_rainfall_mm: number | null;
  sensor_quality: "valid" | "invalid" | null;
  last_ping: string | null;
  observed_at: string | null;
  firmware_version: string | null;
  source: "simulator" | "device" | "unverified" | "none";
  source_class: "physical_device" | "simulator" | "unverified";
  source_trusted: boolean;
  depth_source_class: "physical_device" | "simulator" | "unverified";
  depth_source_trusted: boolean;
  depth_source_id: string | null;
  stream: "operational";
  threshold_advisory_cm: number;
  threshold_warning_cm: number;
  threshold_evacuate_cm: number;
  history: MonitoringSample[];
};

export type MonitoringSnapshot = {
  service_health?:{status:string;checked_at:string;message:string;codes:string[]}|null;
  checked_at: string;
  stale_after_seconds: number;
  stations: MonitoringStation[];
};

// Display retained readings as history when their original heartbeat expires.
// Do not replace the server timestamp or turn an unavailable feed back online.
export function monitoringStationForDisplay(station: MonitoringStation, checkedAt: string,
  staleAfterSeconds: number, nowMs: number, unavailable = false): MonitoringStation {
  const checkedMs = Date.parse(checkedAt);
  const elapsed = Number.isFinite(checkedMs) ? Math.max(0, (nowMs-checkedMs)/1000) : NaN;
  const age = (value:number|null|undefined) => typeof value === "number" && Number.isFinite(value) && Number.isFinite(elapsed) ? value+Math.floor(elapsed) : null;
  const heartbeatAge=age(station.heartbeat_age_seconds), depthAge=age(station.depth_age_seconds),sampleAge=age(station.latest_sample_age_seconds),rainAge=age(station.rainfall_age_seconds);
  const online = station.is_online && !unavailable && heartbeatAge !== null && heartbeatAge <= staleAfterSeconds;
  const administrative = ["inactive", "maintenance", "no_data"].includes(station.connection_status);
  const connection = administrative ? station.connection_status : online ? "online" : "offline";
  const depthFresh=Boolean(station.depth_fresh && online && depthAge!==null && depthAge<=staleAfterSeconds && station.sensor_quality==="valid" && !station.hazard_review_required);
  const depthStatus=station.current_depth_cm===null || depthAge===null ? "missing" : depthAge>staleAfterSeconds ? "stale" : depthFresh ? "fresh" : "retained";
  return {...station, channel_health:ageChannels(station.channel_health,elapsed,staleAfterSeconds,unavailable),
    trend:depthFresh ? station.trend : "unknown",
    rise_rate_cm_per_minute:depthFresh?station.rise_rate_cm_per_minute:null,
    rise_rate_lower:depthFresh?station.rise_rate_lower:null,rise_rate_upper:depthFresh?station.rise_rate_upper:null,
    trend_reason:depthFresh ? station.trend_reason : "Latest depth unavailable or stale; current trend unknown", age_seconds:depthAge, depth_age_seconds:depthAge, heartbeat_age_seconds:heartbeatAge,
    latest_sample_age_seconds:sampleAge,rainfall_age_seconds:rainAge,heartbeat_fresh:online,
    depth_fresh:depthFresh,depth_status:depthStatus,rainfall_fresh:Boolean(station.rainfall_fresh && !unavailable && rainAge!==null && rainAge<=30),
    is_online:online, is_stale:depthStatus==="stale"||depthStatus==="retained", connection_status:connection,connection_unconfirmed:unavailable,
    hazard_state:station.active_alert_id&&!depthFresh?"unresolved":station.hazard_state};
}

// A retained snapshot is history, not proof that the feed is still connected.
export function monitoringSourceIsFresh(
  snapshot: MonitoringSnapshot | null,
  source: "device" | "simulator",
  nowMs: number,
  unavailable = false,
) {
  if (!snapshot || unavailable) return false;
  return snapshot.stations.some(station => {
    const view=monitoringStationForDisplay(station,snapshot.checked_at,snapshot.stale_after_seconds,nowMs,unavailable);
    return view.source===source && view.depth_fresh && (source!=="device" ||
      (view.source_class==="physical_device" && view.source_trusted && view.depth_source_trusted));
  });
}

export function monitoringSourceLabel(station: Pick<MonitoringStation,"source_class"|"source_trusted">) {
  return station.source_class==="physical_device" && station.source_trusted ? "Authenticated registered device"
    : station.source_class==="simulator" ? "Virtual station feed" : "Unregistered source";
}

export function ageLabel(seconds: number | null, connection: MonitoringStation["connection_status"]) {
  if (seconds === null) return connection === "no_data" ? "No readings yet" : "Unknown";
  if (seconds < 60) return `${seconds} sec ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  return `${hours} hr${hours === 1 ? "" : "s"} ago`;
}
