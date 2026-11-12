import {publishedForecastFields} from './forecast-contract.generated';
export const forecastLabels = {
  unavailable:'Forecast unavailable',
  not_trained: "Model not trained", insufficient_data: "Insufficient history", stale_data: "Readings are stale",
  invalid_data: "Invalid readings", available: "Forecast available", service_error: "Service unavailable",
} as const;
export type ForecastStatus = keyof typeof forecastLabels;
export type ForecastUncertainty={method:'calibration_event_max_absolute_residual_all_horizons';nominal_coverage:number;withheld_event_coverage:number;calibration_events:number;test_events:number;policy_sha256:string;display_resolution_cm:number;notice:string};
export type Prediction = {
  uncertainty?:ForecastUncertainty|null;
  ingress_identity?:string|null;registry_version?:number|null;forecast_id?:string|null;deployment_version?:number|null;configuration_hash?:string|null;reference_datum?:string|null;model_card_id?:string|null;data_cutoff?:string|null;measurement_source?:string|null;
  schema_version: "1.0"; station_id: string; status: ForecastStatus; reason: string;
  source: "none" | "model" | "simulated"; advisory_only: true;
  checked_at: string; generated_at: string | null; valid_until: string | null; model_version: string | null;
  input_status: "usable" | "insufficient_data" | "stale_data" | "invalid_data";
  input_window_start: string | null; input_last_recorded_at: string | null;
  sample_count: number; valid_sample_count: number; preview_allowed: boolean;
  timestamp_basis: "server_received" | "device_measured" | "synthetic";
  rainfall_interval_seconds: number | null;
  forecasts: { horizon_minutes: 30 | 60 | 90; target_at: string | null; water_depth_cm: number | null;lower_depth_cm?:number|null;upper_depth_cm?:number|null }[];
};

// Fail closed when the adapter/API contract changes or returns malformed values.
export function parsePrediction(value: unknown): Prediction {
  const p = value as Prediction;
  const date = (v: unknown): v is string => typeof v === "string"
    && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(v)
    && Number.isFinite(Date.parse(v));
  const nullableDate = (v: unknown) => v === null || date(v);
  const count = (v: unknown): v is number => typeof v === "number" && Number.isSafeInteger(v) && v >= 0;
  if (!p || p.schema_version !== "1.0" || p.advisory_only !== true || !Object.hasOwn(forecastLabels, p.status)
    || !["none", "model", "simulated"].includes(p.source) || typeof p.station_id !== "string"
    || typeof p.reason !== "string" || !date(p.checked_at) || typeof p.preview_allowed !== "boolean"
    || !(p.model_version === null || (typeof p.model_version === "string" && p.model_version.trim().length > 0))
    || !["usable", "insufficient_data", "stale_data", "invalid_data"].includes(p.input_status)
    || !["server_received", "device_measured", "synthetic"].includes(p.timestamp_basis)
    || !nullableDate(p.generated_at) || !nullableDate(p.valid_until)
    || !nullableDate(p.input_window_start) || !nullableDate(p.input_last_recorded_at)
    || !count(p.sample_count) || !count(p.valid_sample_count) || p.valid_sample_count > p.sample_count
    || !(p.rainfall_interval_seconds === null || Number.isSafeInteger(p.rainfall_interval_seconds))
    || !Array.isArray(p.forecasts) || p.forecasts.length !== 3
    || p.forecasts.some((v, i) => !v || v.horizon_minutes !== [30, 60, 90][i])) throw new Error("The forecast response could not be validated.");
  if (p.status === "available") {
    if (p.source === "none" || !date(p.generated_at) || !date(p.input_last_recorded_at) || !date(p.valid_until)
      || Date.parse(p.valid_until!) <= Date.parse(p.checked_at)
      || p.forecasts.some((v) => typeof v.water_depth_cm !== "number" || !Number.isFinite(v.water_depth_cm) || v.water_depth_cm < 0 || v.water_depth_cm > 1000 || !date(v.target_at)
        || Date.parse(v.target_at) !== Date.parse(p.input_last_recorded_at!) + v.horizon_minutes * 60000)) throw new Error("The forecast response could not be validated.");
  } else if (p.forecasts.some((v) => v.water_depth_cm !== null || v.target_at !== null || v.lower_depth_cm!=null || v.upper_depth_cm!=null)) throw new Error("Unavailable forecasts contained unexpected values.");
  if ((p.source === "simulated") !== (p.timestamp_basis === "synthetic")) throw new Error("The forecast provenance could not be validated.");
  if (p.source === "model" && (p.status !== "available" || typeof p.model_version !== "string"
    || p.input_status !== "usable" || !date(p.input_window_start) || p.sample_count === 0
    || p.valid_sample_count !== p.sample_count
    || Date.parse(p.input_window_start) > Date.parse(p.input_last_recorded_at!)
    || Date.parse(p.input_last_recorded_at!) > Date.parse(p.generated_at!)
    || Date.parse(p.generated_at!) > Date.parse(p.checked_at))) throw new Error("The model forecast input metadata could not be validated.");
  if (p.source === "simulated" && p.model_version !== null) throw new Error("A sample preview cannot claim a trained model.");
  return p;
}

export function parsePublishedPrediction(value:unknown):Prediction {
  const p=parsePrediction(value);
  if(p.status==='available'&&(publishedForecastFields.some(key=>p[key]===undefined||p[key]===null)||typeof p.ingress_identity!=='string'||!p.ingress_identity||!Number.isSafeInteger(p.registry_version)||Number(p.registry_version)<1||p.source!=='model'||p.timestamp_basis!=='device_measured'||p.model_card_id!==p.model_version||!p.forecast_id||!/^[-a-f0-9]{36}$/.test(p.forecast_id)||!Number.isSafeInteger(p.deployment_version)||Number(p.deployment_version)<1
    ||!p.reference_datum||!p.configuration_hash||!p.model_card_id||!/^[a-f0-9]{64}$/.test(p.configuration_hash)||!/^[a-f0-9]{64}$/.test(p.model_card_id)
    ||p.data_cutoff!==p.input_last_recorded_at||p.measurement_source!=='registry_verified_physical_device'))throw Error('Published forecast identity or provenance is incomplete.');
  if(p.status==='available'){
    const u=p.uncertainty;
    if(!u||u.method!=='calibration_event_max_absolute_residual_all_horizons'||!Number.isFinite(u.nominal_coverage)||u.nominal_coverage<.8||u.nominal_coverage>.99||!Number.isFinite(u.withheld_event_coverage)||u.withheld_event_coverage<0||u.withheld_event_coverage>1||!Number.isInteger(u.calibration_events)||u.calibration_events<1||!Number.isInteger(u.test_events)||u.test_events<1||!/^[a-f0-9]{64}$/.test(u.policy_sha256)||!Number.isFinite(u.display_resolution_cm)||u.display_resolution_cm<=0||u.display_resolution_cm>100||p.forecasts.some(point=>typeof point.lower_depth_cm!=='number'||typeof point.upper_depth_cm!=='number'||!Number.isFinite(point.lower_depth_cm)||!Number.isFinite(point.upper_depth_cm)||point.lower_depth_cm<0||point.upper_depth_cm>1000||point.lower_depth_cm>point.water_depth_cm!||point.upper_depth_cm<point.water_depth_cm!))throw Error('Published forecast uncertainty is incomplete.');
  }
  return p;
}

export function forecastDepth(value:number|null|undefined,resolution=1){
  if(value==null)return '—';
  const step=Math.max(1,resolution);return `≈${(Math.round(value/step)*step).toFixed(0)}`;
}
export function forecastInterval(lower:number|null|undefined,upper:number|null|undefined){return lower==null||upper==null?'Uncertainty unavailable':`${Math.floor(lower)}–${Math.ceil(upper)} cm`;}

export function forecastTime(value: string | null) {
  return value ? new Date(value).toLocaleString("en-PH", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "Asia/Manila" }) : "—";
}
