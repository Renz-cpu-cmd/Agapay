import type { Station } from "@/data/mockData";

// Public Urdaneta City center, not a station or resident location.
export const cityMapCenter: [number, number] = [15.9759995, 120.5668992];
export const cityMapZoom = 13;
export const googleCityMapLink = "https://www.google.com/maps/@15.9760,120.5669,13z";

export type MapTileStatus = "loading" | "ready" | "partial" | "error";

export function stationCoordinates(station: Station): [number, number] | null {
  const point = station.coordinates;
  if (!point || !Number.isFinite(point.latitude) || !Number.isFinite(point.longitude)
    || Math.abs(point.latitude) > 90 || Math.abs(point.longitude) > 180) return null;
  return [point.latitude, point.longitude];
}
