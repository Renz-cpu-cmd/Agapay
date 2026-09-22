export const forecastLabels = {
  not_trained: "Model not trained", insufficient_data: "Insufficient history", stale_data: "Readings are stale",
  invalid_data: "Invalid readings", available: "Forecast available", service_error: "Service unavailable",
} as const;
export type ForecastStatus = keyof typeof forecastLabels;
export type Prediction = {
  schema_version: "1.0"; station_id: string; status: ForecastStatus; reason: string;
  source: "none" | "model" | "simulated"; advisory_only: true;
  checked_at: string; generated_at: string | null; valid_until: string | null; model_version: string | null;
  input_status: "usable" | "insufficient_data" | "stale_data" | "invalid_data";
  input_window_start: string | null; input_last_recorded_at: string | null;
  sample_count: number; valid_sample_count: number; preview_allowed: boolean;
  timestamp_basis: "server_received" | "device_measured" | "synthetic";
  rainfall_interval_seconds: number | null;
  forecasts: { horizon_minutes: 30 | 60 | 90; target_at: string | null; water_depth_cm: number | null }[];
};

// Fail closed when the adapter/API contract changes or returns malformed values.
export function parsePrediction(value: unknown): Prediction {
  const p = value as Prediction;
  const date = (v: unknown) => typeof v === "string" && Number.isFinite(Date.parse(v));
  if (!p || p.schema_version !== "1.0" || p.advisory_only !== true || !Object.hasOwn(forecastLabels, p.status)
    || !["none", "model", "simulated"].includes(p.source) || typeof p.station_id !== "string"
    || typeof p.reason !== "string" || !date(p.checked_at) || typeof p.preview_allowed !== "boolean"
    || !Array.isArray(p.forecasts) || p.forecasts.length !== 3
    || p.forecasts.some((v, i) => !v || v.horizon_minutes !== [30, 60, 90][i])) throw new Error("The forecast response could not be validated.");
  if (p.status === "available") {
    if (p.source === "none" || !date(p.generated_at) || !date(p.input_last_recorded_at) || !date(p.valid_until)
      || Date.parse(p.valid_until!) <= Date.parse(p.checked_at)
      || (p.source === "model" && !p.model_version)
      || p.forecasts.some((v) => typeof v.water_depth_cm !== "number" || !Number.isFinite(v.water_depth_cm) || v.water_depth_cm < 0 || v.water_depth_cm > 1000 || !date(v.target_at))) throw new Error("The forecast response could not be validated.");
  } else if (p.forecasts.some((v) => v.water_depth_cm !== null || v.target_at !== null)) throw new Error("Unavailable forecasts contained unexpected values.");
  if (p.source === "simulated" && p.model_version !== null) throw new Error("A sample preview cannot claim a trained model.");
  return p;
}

export function forecastTime(value: string | null) {
  return value ? new Date(value).toLocaleString("en-PH", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "Asia/Manila" }) : "—";
}
