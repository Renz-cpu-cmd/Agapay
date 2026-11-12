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
    + ` · Measured: ${station.depth.measuredAt ?? "unknown"} · ${station.sourceTrusted && station.depthSourceTrusted ? "Registry-verified physical source" : "Unverified / test source"}`
    + ` · Station datum: ${station.channelHealth?.calibration.reference_datum ?? "unconfirmed"}`;
}

/** R1 location wording; never implies a position the registry does not hold. */
export function locationLabel(station: Station): string {
  if (!stationCoordinates(station)) {
    return station.coordinateStatus === "invalid"
      ? "Recorded location invalid · no map pin"
      : "Location unavailable · no map pin";
  }
  return station.coordinates?.status === "verified" ? "Confirmed registry location"
    : station.coordinates?.status === "planned" ? "Planned demo location"
    : "Unconfirmed registry location";
}

export function stationCoordinates(station: Station): [number, number] | null {
  const point = station.coordinates;
  if (!point || !Number.isFinite(point.latitude) || !Number.isFinite(point.longitude)
    || Math.abs(point.latitude) > 90 || Math.abs(point.longitude) > 180) return null;
  return [point.latitude, point.longitude];
}
