export type AlertSeverity = "NORMAL" | "ADVISORY" | "WARNING" | "EVACUATE";
export type IncidentSeverity = Exclude<AlertSeverity, "NORMAL">;
export type AlertStatus = "ACTIVE" | "RESOLVED";

export interface SensorAlert {
  id: number;
  station_id: string;
  current_severity: AlertSeverity;
  highest_severity: IncidentSeverity;
  status: AlertStatus;
  source: "sensor";
  trigger_telemetry_id: number;
  latest_telemetry_id: number;
  trigger_sequence_no: number;
  latest_sequence_no: number;
  trigger_depth_cm: number;
  latest_depth_cm: number;
  triggered_at: string;
  last_transition_at: string;
  resolved_at: string | null;
}

export interface AlertTransition {
  id: number;
  alert_id: number;
  station_id: string;
  telemetry_id: number;
  sequence_no: number;
  previous_severity: AlertSeverity;
  new_severity: AlertSeverity;
  water_depth_cm: number;
  transitioned_at: string;
}

export interface AlertPage<T> { items: T[]; total: number }
export const ALERT_PAGE_SIZE = 50;

export function alertListPath(status: AlertStatus, station: string, severity: string, offset: number) {
  const query = new URLSearchParams({ limit: String(ALERT_PAGE_SIZE), offset: String(offset) });
  if (station !== "All") query.set("station_id", station);
  if (status === "RESOLVED") query.set("status", status);
  // The API severity filter uses CURRENT severity (NORMAL after resolution).
  // Historical peak-tier filtering is therefore local to the retrieved page.
  else if (severity !== "All") query.set("severity", severity);
  return `${status === "ACTIVE" ? "alerts/active" : "alerts"}?${query}`;
}

export function incidentSeverity(alert: SensorAlert): AlertSeverity {
  return alert.status === "RESOLVED" ? alert.highest_severity : alert.current_severity;
}

const philippineTime = new Intl.DateTimeFormat("en-PH", {
  timeZone: "Asia/Manila", year: "numeric", month: "short", day: "2-digit",
  hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
});
export function alertTime(value: string | null) {
  return value ? `${philippineTime.format(new Date(value))} PHT` : "—";
}
