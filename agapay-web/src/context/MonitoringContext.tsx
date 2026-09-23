"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { accountRequest } from "@/lib/accounts";
import { ageLabel, type MonitoringSnapshot, type MonitoringStation } from "@/lib/monitoring";
import { alerts as fallbackAlerts, stations as fallbackStations, type Alert, type Station } from "@/data/mockData";

type DataMode = "simulator" | "device" | "no_data" | "demo";

type MonitoringState = {
  stations: Station[];
  // Dashboard current-tier summary only; never persistent alert history.
  sensorAlerts: Alert[];
  snapshot: MonitoringSnapshot | null;
  loading: boolean;
  error: string;
  dataMode: DataMode;
  refresh: () => Promise<void>;
};

const MonitoringContext = createContext<MonitoringState | null>(null);

function displayStation(source: MonitoringStation, fallback?: Station): Station {
  const hasCoordinates = source.latitude !== null && source.longitude !== null;
  const history = source.history.flatMap(sample => sample.sensor_quality === "valid" && sample.water_depth_cm !== null
    ? [{ time: new Date(sample.recorded_at).toLocaleTimeString("en-PH", { hour: "2-digit", minute: "2-digit", timeZone: "Asia/Manila" }), level: sample.water_depth_cm }]
    : []);
  const rainHistory = source.history.map(sample => ({
    time: new Date(sample.recorded_at).toLocaleTimeString("en-PH", { hour: "2-digit", minute: "2-digit", timeZone: "Asia/Manila" }),
    value: sample.rainfall_mm,
  }));
  return {
    id: source.station_id,
    name: source.station_name,
    location: [source.barangay, source.municipality].filter(Boolean).join(", ") || fallback?.location || "Location unavailable",
    barangay: source.barangay || fallback?.barangay || "Unavailable",
    status: source.alert_tier ?? "UNKNOWN",
    waterLevel: source.current_depth_cm ?? 0,
    rainfall: source.latest_rainfall_mm ?? 0,
    trend: source.trend,
    lastPing: ageLabel(source.age_seconds, source.connection_status),
    firmware: source.firmware_version ?? "Unavailable",
    sensorValid: source.sensor_quality === "valid",
    isOnline: source.is_online,
    coordinates: hasCoordinates ? { latitude: source.latitude!, longitude: source.longitude!, status: "planned" } : fallback?.coordinates ?? null,
    thresholds: {
      advisory: source.threshold_advisory_cm,
      warning: source.threshold_warning_cm,
      evacuate: source.threshold_evacuate_cm,
    },
    waterHistory: history,
    rainHistory,
    dataSource: source.source,
    connectionStatus: source.connection_status,
    observedAt: source.observed_at,
  };
}

function mergeStations(snapshot: MonitoringSnapshot | null) {
  if (!snapshot) return fallbackStations;
  const sourceById = new Map(snapshot.stations.map(station => [station.station_id, station]));
  const merged = fallbackStations.flatMap(station => {
    const source = sourceById.get(station.id);
    if (!source) return [];
    sourceById.delete(station.id);
    return [displayStation(source, station)];
  });
  for (const source of sourceById.values()) merged.push(displayStation(source));
  return merged;
}

function alertsFor(stations: Station[]): Alert[] {
  return stations.flatMap(station => station.dataSource !== "none" && !["NORMAL", "UNKNOWN"].includes(station.status)
    ? [{
        id: `SENSOR-${station.id}`,
        stationId: station.id,
        stationName: station.name,
        tier: station.status,
        waterLevel: station.waterLevel,
        triggeredAt: station.observedAt ? new Date(station.observedAt).toLocaleTimeString("en-PH", { hour: "2-digit", minute: "2-digit", timeZone: "Asia/Manila" }) : "—",
        status: "ACTIVE" as const,
        triggeredAgo: station.lastPing,
        message: station.sensorValid
          ? `Generated from the latest valid ${station.dataSource === "simulator" ? "virtual-station" : "device"} reading.`
          : "Severity preserved from the last valid reading; the latest sensor sample is invalid.",
      }]
    : []);
}

export function MonitoringProvider({ children }: { children: ReactNode }) {
  const [snapshot, setSnapshot] = useState<MonitoringSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const active = useRef(true);
  const inFlight = useRef(false);

  const refresh = useCallback(async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    try {
      const next = await accountRequest<MonitoringSnapshot>("monitoring/stations?history_limit=120");
      if (active.current) { setSnapshot(next); setError(""); }
    } catch (reason) {
      if (active.current) setError(reason instanceof Error ? reason.message : "Monitoring data is unavailable.");
    } finally {
      inFlight.current = false;
      if (active.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    active.current = true;
    void refresh();
    const timer = window.setInterval(() => { if (!document.hidden) void refresh(); }, 5000);
    return () => { active.current = false; window.clearInterval(timer); };
  }, [refresh]);

  const stations = useMemo(() => mergeStations(snapshot), [snapshot]);
  const sensorAlerts = useMemo(() => snapshot ? alertsFor(stations) : fallbackAlerts.filter(alert => alert.status === "ACTIVE"), [snapshot, stations]);
  const dataMode: DataMode = !snapshot ? "demo" : snapshot.stations.some(station => station.source === "simulator")
    ? "simulator" : snapshot.stations.some(station => station.source === "device") ? "device" : "no_data";

  return <MonitoringContext.Provider value={{ stations, sensorAlerts, snapshot, loading, error, dataMode, refresh }}>{children}</MonitoringContext.Provider>;
}

export function useMonitoring() {
  const context = useContext(MonitoringContext);
  if (!context) throw new Error("useMonitoring requires MonitoringProvider");
  return context;
}
