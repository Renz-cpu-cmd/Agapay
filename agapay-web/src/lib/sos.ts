export type SosStatus = "ACTIVE" | "ACKNOWLEDGED" | "RESOLVED";
export type SosRequest = {
  id: number;
  request_id: string;
  resident_name: string;
  phone: string;
  barangay: string;
  location: string;
  message: string;
  latitude: number | null;
  longitude: number | null;
  location_source: "gps" | "manual";
  accuracy_m: number | null;
  location_recorded_at: string | null;
  practice: boolean;
  status: SosStatus;
  created_at: string;
  acknowledged_by_name: string | null;
  acknowledged_at: string | null;
  resolved_by_name: string | null;
  resolved_at: string | null;
  resolution_note: string | null;
};
export type SosPage = { items: SosRequest[]; total: number; counts: Record<SosStatus, number> };
export function sosTime(value: string | null) {
  return value ? new Date(value).toLocaleString("en-PH", { month: "short", day: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit", timeZone: "Asia/Manila" }) : "—";
}
