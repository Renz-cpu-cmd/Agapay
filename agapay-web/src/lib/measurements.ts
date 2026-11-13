import { readingLabel } from "./operational-vocabulary";
import type { Station } from "../data/mockData";
import type { MonitoringStation } from "./monitoring";

export type MeasurementState = "current" | "retained" | "stale" | "missing" | "invalid" | "unverified" | "exercise" | "review";
export interface Measurement {
  value: number | null;
  measuredAt: string | null;
  ageSeconds: number | null;
  state: MeasurementState;
  quality: "valid" | "invalid" | "unknown";
  reason: string;
  latestSampleQuality: "valid" | "invalid" | "unknown";
}

export function stationMeasurement(source: MonitoringStation, channel: "depth" | "rain"): Measurement {
  if(channel==="rain") {
    const p=source.rainfall_product;
    const timed=Boolean(p?.interval_start&&p.interval_end&&Number.isFinite(Date.parse(p.interval_start))&&Number.isFinite(Date.parse(p.interval_end)));
    const value=timed&&p?.quality==="partial"&&p.rainfall_mm!=null&&Number.isFinite(p.rainfall_mm)?p.rainfall_mm:null;
    const current=value!==null&&source.rainfall_fresh;
    return {value,measuredAt:source.rainfall_observed_at??null,ageSeconds:source.rainfall_age_seconds??null,
      state:value===null?"missing":current?"current":"stale",quality:value===null?"unknown":"valid",latestSampleQuality:value===null?"unknown":"valid",
      reason:p?`Journal received tips · ${p.interval_start??"—"} to ${p.interval_end??"—"} · ${p.source} · ${p.coverage} · calibration ${p.calibration_version??"unknown"}; incomplete hour, not an hourly model input`:
        "Rainfall interval/source unavailable; deprecated water telemetry rainfall excluded"};
  }
  const depth = channel === "depth";
  const raw = depth ? source.current_depth_cm : source.latest_rainfall_mm;
  const value = raw != null && Number.isFinite(raw) ? raw : null;
  const measuredAt = depth ? source.last_valid_depth_at : source.rainfall_observed_at;
  const ageSeconds = depth ? source.depth_age_seconds : source.rainfall_age_seconds;
  // Rainfall quality is independent of the ultrasonic channel.
  const quality = depth ? source.sensor_quality ?? "unknown" : value === null ? "unknown" : "valid";
  let state: MeasurementState;
  let reason: string;
  if (value === null) {
    state = quality === "invalid" ? "invalid" : "missing";
    reason = state === "invalid" ? "Latest sensor sample invalid; no valid depth available" : "No measurement received";
  } else if (!measuredAt || !Number.isFinite(Date.parse(measuredAt)) || ageSeconds === null) {
    state = "retained"; reason = "Measurement time unavailable; excluded from current statistics";
  } else if (depth && source.hazard_review_required) {
    state = "review"; reason = "Sensor plausibility review required; excluded from current statistics";
  } else if (quality === "invalid") {
    state = "retained"; reason = "Latest sensor sample invalid; showing last valid depth";
  } else if (source.source_class === "simulator") {
    state = "exercise"; reason = "Exercise sample; excluded from operational statistics";
  } else if (source.source_class !== "physical_device" || !source.source_trusted || (depth && !source.depth_source_trusted)) {
    state = "unverified"; reason = "Unverified source; excluded from operational statistics";
  } else if (!(depth ? source.depth_fresh : source.rainfall_fresh)) {
    state = "stale"; reason = "Measurement stale or feed unavailable; last known value";
  } else {
    state = "current"; reason = "Fresh valid measurement";
  }
  return { value, measuredAt: measuredAt ?? null, ageSeconds: ageSeconds ?? null, state, quality: value !== null ? "valid" : quality, latestSampleQuality: quality, reason };
}

export function measurementText(measurement: Measurement, digits = 1, unit = ""): string {
  return measurement.value === null ? "—" : `${measurement.value.toFixed(digits)}${unit ? ` ${unit}` : ""}`;
}
export function measurementLabel(measurement: Measurement): string {
  return readingLabel(measurement.value, measurement.state === "current", measurement.measuredAt);
}
export function measurementNote(measurement: Measurement): string {
  return `${measurementLabel(measurement)} · ${measurement.reason} · Value quality ${measurement.quality} (latest sample ${measurement.latestSampleQuality}) · Measured ${measurement.measuredAt ?? "—"}`;
}
export function measurementPercent(measurement: Measurement, maximum: number): string {
  return measurement.value === null ? "0%" : `${Math.max(0, Math.min(100, measurement.value / maximum * 100))}%`;
}
export function currentDepthSummary(stations: Station[]) {
  const available = stations.filter(station => station.depth.state === "current" && station.depth.value !== null);
  const values = available.map(station => station.depth.value!);
  return {
    available, coverage: `${available.length}/${stations.length} stations with current valid depth`,
    maximum: values.length ? Math.max(...values) : null,
    minimum: values.length ? Math.min(...values) : null,
    average: values.length ? values.reduce((a, b) => a + b, 0) / values.length : null,
  };
}

// The on-screen report and CSV use these same rows, including missing-data reasons.
export function measurementReport(station: Station, stations: Station[]): string[][] {
  const samples = station.waterHistory.filter(point => point.level !== null);
  const max = samples.length ? Math.max(...samples.map(point => point.level!)) : null;
  const tier = max === null ? "UNKNOWN" : max >= station.thresholds.evacuate ? "EVACUATE"
    : max >= station.thresholds.warning ? "WARNING" : max >= station.thresholds.advisory ? "ADVISORY" : "NORMAL";
  const summary = currentDepthSummary(stations);
  return [
    ["Station", station.id], ["Barangay", station.barangay],
    ["Source", station.sourceTrusted ? "Authenticated registered device" : "Unverified / exercise source"],
    ["Water depth", measurementText(station.depth, 1, "cm")],
    ["Depth state / reason / time", measurementNote(station.depth)],
    ["Depth age", station.measurementAge ?? "Unknown"],
    ["Rainfall received this UTC hour", measurementText(station.rain, 3, "mm")],
    ["Rainfall state / reason / time", measurementNote(station.rain)],
    ["Rainfall age seconds", station.rain.ageSeconds?.toString() ?? "—"],
    ["Recorded window maximum depth", max === null ? "—" : `${max.toFixed(1)} cm`],
    ["Recorded window maximum tier", tier],
    ["Recorded window depth coverage", `${samples.length}/${station.waterHistory.length} valid samples`],
    ["Current depth coverage", summary.coverage],
    ["Current maximum depth", summary.maximum === null ? "—" : `${summary.maximum.toFixed(1)} cm`],
    ["Current minimum depth", summary.minimum === null ? "—" : `${summary.minimum.toFixed(1)} cm`],
    ["Current average depth", summary.average === null ? "—" : `${summary.average.toFixed(1)} cm`],
    ["Latest heartbeat time", station.heartbeatAt ?? "—"], ["Heartbeat age", station.lastPing],
    ["Hazard state", station.hazardState ?? "unknown"],
  ];
}
