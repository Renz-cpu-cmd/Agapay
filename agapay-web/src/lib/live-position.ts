import type { MonitoringStation } from "./monitoring";

/** Migration 0010: staff-only GPS position reported by the phone carrying a portable station. */
export type LivePositionView = {
  latitude: number;
  longitude: number;
  accuracyM: number;
  capturedAt: string;
  ageSeconds: number;
  fresh: boolean;
  trackingActive: boolean;
};

/** Server accuracy limit; anything coarser is never drawn as a station position. */
export const MAX_LIVE_ACCURACY_M = 50;

export function livePosition(source: MonitoringStation["live_position"]): LivePositionView | null {
  if (!source) return null;
  const { latitude, longitude, accuracy_m: accuracyM, age_seconds: ageSeconds } = source;
  if (![latitude, longitude, accuracyM, ageSeconds].every(value => typeof value === "number" && Number.isFinite(value))) return null;
  if (Math.abs(latitude) > 90 || Math.abs(longitude) > 180 || accuracyM <= 0 || accuracyM > MAX_LIVE_ACCURACY_M || ageSeconds < 0) return null;
  return {
    latitude, longitude, accuracyM, ageSeconds,
    capturedAt: source.captured_at,
    fresh: source.fresh === true,
    trackingActive: source.tracking_active === true,
  };
}

export function liveAge(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)} s ago`;
  if (seconds < 3600) return `${Math.round(seconds / 60)} min ago`;
  if (seconds < 172800) return `${Math.round(seconds / 3600)} h ago`;
  return `${Math.round(seconds / 86400)} days ago`;
}

export function isLive(live: LivePositionView): boolean {
  return live.fresh && live.trackingActive;
}

/** Wording never presents an old or ended fix as the station's current position. */
export function liveLabel(live: LivePositionView): string {
  const accuracy = `±${Math.round(live.accuracyM)} m`;
  if (isLive(live)) return `Live phone GPS · ${accuracy} · ${liveAge(live.ageSeconds)}`;
  if (live.trackingActive) return `Tracking active · no recent fix · last ${accuracy} ${liveAge(live.ageSeconds)}`;
  return `Last known phone GPS · ${accuracy} · ${liveAge(live.ageSeconds)}`;
}
