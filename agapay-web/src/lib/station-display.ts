import { ageLabel, type MonitoringStation } from "./monitoring";
import type { Station } from "../data/mockData";
import { stationMeasurement } from "./measurements";
import { livePosition } from "./live-position";

/**
 * R1: the registry is the only source of an operational station position. A missing,
 * half-missing, non-finite or out-of-range pair yields no point; zero is a valid value.
 * No bundled, demo or "planned" coordinate is ever substituted.
 */
export function registryLocation(source: Pick<MonitoringStation, "latitude" | "longitude" | "coordinate_status">
  & Partial<Pick<MonitoringStation, "coordinate_precision_m" | "coordinate_basis">>):
  { coordinates: Station["coordinates"]; status: NonNullable<Station["coordinateStatus"]> } {
  const { latitude, longitude } = source;
  // The server nulls an invalid stored pair; its explicit state takes precedence.
  if (source.coordinate_status === "invalid") return { coordinates: null, status: "invalid" };
  if (latitude === null && longitude === null || source.coordinate_status === "missing") {
    return { coordinates: null, status: "missing" };
  }
  if (typeof latitude !== "number" || typeof longitude !== "number" || !Number.isFinite(latitude)
    || !Number.isFinite(longitude) || Math.abs(latitude) > 90 || Math.abs(longitude) > 180) {
    return { coordinates: null, status: "invalid" };
  }
  // Absent status (older server) fails closed to unverified.
  const status = source.coordinate_status === "verified" ? "verified" : "unverified";
  // A7.1: precision is passed through only for a mappable pair; it never creates a point.
  const precisionM = typeof source.coordinate_precision_m === "number" && Number.isFinite(source.coordinate_precision_m)
    ? source.coordinate_precision_m : null;
  return { coordinates: { latitude, longitude, status, precisionM, basis: precisionM === null ? null : source.coordinate_basis ?? null }, status };
}

export function displayStation(source: MonitoringStation): Station {
  const location = registryLocation(source);
  const history = source.history.map(sample => ({ time: new Date(sample.recorded_at).toLocaleTimeString("en-PH", { hour: "2-digit", minute: "2-digit", second:"2-digit", timeZone: "Asia/Manila" }), level: sample.sensor_quality === "valid" ? sample.water_depth_cm : null, recordedAt:sample.recorded_at,measuredAt:sample.measured_at??null,receivedAt:sample.received_at??null }));
  const rainHistory = source.history.map(sample => ({
    time: new Date(sample.recorded_at).toLocaleTimeString("en-PH", { hour: "2-digit", minute: "2-digit", timeZone: "Asia/Manila" }),
    value: null, recordedAt: sample.recorded_at,
  }));
  return {
    id: source.station_id,
    name: source.station_name,
    location: [source.barangay, source.municipality].filter(Boolean).join(", ") || "Location unavailable",
    barangay: source.barangay || "Unavailable",
    status: source.alert_tier ?? "UNKNOWN",
    depth: stationMeasurement(source, "depth"),
    rain: stationMeasurement(source, "rain"),
    trend: source.trend,
    administrativeStatus:source.administrative_status ?? "unknown",channelHealth:source.channel_health ?? undefined,configuration:source.configuration,lifecycle:source.lifecycle,
    riseRate:source.rise_rate_cm_per_minute,riseRateLower:source.rise_rate_lower,riseRateUpper:source.rise_rate_upper,
    trendReason:source.trend_reason,trendCoverage:source.trend_coverage,
    lastPing: ageLabel(source.heartbeat_age_seconds, source.connection_status),
    measurementAge: ageLabel(source.depth_age_seconds, source.connection_status),
    heartbeatAt:source.heartbeat_at,
    depthFresh:source.depth_fresh,depthStatus:source.depth_status,
    depthAgeSeconds:source.depth_age_seconds,heartbeatAgeSeconds:source.heartbeat_age_seconds,
    hazardState:source.hazard_state,activeHazardTier:source.active_hazard_tier,
    observationTier:source.observation_tier,hazardPolicyState:source.hazard_policy_state,hazardDecision:source.hazard_decision,
    sourceClass:source.source_class,sourceTrusted:source.source_trusted,
    depthSourceTrusted:source.depth_source_trusted,depthSourceId:source.depth_source_id,
    firmware: source.firmware_version ?? "Unavailable",
    sensorValid: source.sensor_quality === "valid",
    isOnline: source.is_online,
    coordinates: location.coordinates,
    coordinateStatus: location.status,
    livePosition: livePosition(source.live_position),
    thresholds: {
      advisory: source.threshold_advisory_cm,
      warning: source.threshold_warning_cm,
      evacuate: source.threshold_evacuate_cm,
    },
    waterHistory: history,
    rainHistory,
    dataSource: source.source,
    connectionStatus: source.connection_unconfirmed ? "unconfirmed" : source.connection_status,
    observedAt: source.last_valid_depth_at,
  };
}

