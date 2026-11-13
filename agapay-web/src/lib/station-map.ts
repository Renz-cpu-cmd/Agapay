import type { AlertTier, Station } from "@/data/mockData";
import { measurementLabel } from "./measurements";

// Public Urdaneta City center, not a station or resident location.
export const cityMapCenter: [number, number] = [15.9759995, 120.5668992];
export const cityMapZoom = 13;
export const googleCityMapLink = "https://www.google.com/maps/@15.9760,120.5669,13z";

export type MapTileStatus = "loading" | "ready" | "partial" | "error";

export function stationMarkerTier(station: Station): AlertTier {
  return !station.isOnline ? "OFFLINE" : station.depthFresh ? station.status : "UNKNOWN";
}

export function stationStatusDescription(station: Station): string {
  return `Observation tier: ${station.depth.state === "current" ? station.observationTier ?? station.status : "UNKNOWN"}`
    + ` · Episode tier: ${station.activeHazardTier ?? "None recorded"} (${station.hazardState ?? "unknown"})`
    + ` · Connectivity: ${station.connectionStatus ?? "unknown"} · Heartbeat age: ${station.lastPing ?? "unknown"}`
    + ` · Water depth: ${measurementLabel(station.depth)} · Latest sample validity: ${station.depth.latestSampleQuality}`
    + ` · Measured: ${station.depth.measuredAt ?? "unknown"} · ${station.sourceTrusted && station.depthSourceTrusted ? "Authenticated registered device" : "Unregistered source"}`;
}

/** R1 location wording; never implies a position the registry does not hold. */
export function locationLabel(station: Station): string {
  if (!stationCoordinates(station)) {
    return station.coordinateStatus === "invalid"
      ? "Recorded location invalid · no map pin"
      : "Location unavailable · no map pin";
  }
  const point = station.coordinates;
  if (point?.status === "planned") return "Planned location";
  // A7.1: recorded metadata, never inferred, decides whether the pin is an area.
  const metres = point?.precisionM ?? null;
  if (metres !== null && (point?.basis !== "surveyed" || metres > PRECISE_POINT_RADIUS_M)) {
    const detail = `${metres >= 1000 ? `~${Math.round(metres / 1000)} km` : `~${metres} m`}, ${
      point?.basis === "owner_confirmed" ? "owner-confirmed" : point?.basis === "surveyed" ? "surveyed" : "estimated"}`;
    return point?.status === "verified" ? `Approximate location (${detail})` : `Approximate unconfirmed location (${detail})`;
  }
  if (point?.status !== "verified") return "Unconfirmed registry location";
  return point.basis === "surveyed" && metres !== null
    ? `Confirmed registry location (±${metres} m, surveyed)` : "Confirmed registry location";
}

/** Radius at or below which a surveyed pair may be shown as an exact installation point. */
export const PRECISE_POINT_RADIUS_M = 50;

export function stationCoordinates(station: Station): [number, number] | null {
  const point = station.coordinates;
  if (!point || !Number.isFinite(point.latitude) || !Number.isFinite(point.longitude)
    || Math.abs(point.latitude) > 90 || Math.abs(point.longitude) > 180) return null;
  return [point.latitude, point.longitude];
}
