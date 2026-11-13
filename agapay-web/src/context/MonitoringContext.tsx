"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { accountRequest } from "@/lib/accounts";
import { monitoringStationForDisplay, type MonitoringSnapshot } from "@/lib/monitoring";
import type { Alert, Station } from "@/data/mockData";

import { visiblePoll } from "@/lib/visible-poll";
import { displayStation } from "@/lib/station-display";

type DataMode = "simulator" | "device" | "unverified" | "no_data" | "demo";

type MonitoringState = {
  selectedStationId: string;
  selectStation: (id: string) => void;
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


// R1: operational stations come only from the API registry, in its order. Bundled
// fixtures are never merged in, so no demo coordinate or place name can leak.
function mergeStations(snapshot: MonitoringSnapshot | null, nowMs: number, unavailable: boolean) {
  if (!snapshot) return [];
  return snapshot.stations.map(station => displayStation(
    monitoringStationForDisplay(station,snapshot.checked_at,snapshot.stale_after_seconds,nowMs,unavailable)));
}

function alertsFor(stations: Station[]): Alert[] {
  return stations.flatMap(station => station.dataSource !== "none" && ["observed","unresolved"].includes(station.hazardState??"") && !["NORMAL", "UNKNOWN"].includes(station.status)
    ? [{
        id: `SENSOR-${station.id}`,
        stationId: station.id,
        stationName: station.name,
        tier: station.status,
        waterLevel: station.depth.value,
        triggeredAt: station.observedAt ? new Date(station.observedAt).toLocaleTimeString("en-PH", { hour: "2-digit", minute: "2-digit", timeZone: "Asia/Manila" }) : "—",
        status: "ACTIVE" as const,
        triggeredAgo: station.measurementAge ?? "Unknown",
        message: station.hazardState === "unresolved"
          ? `Unresolved sensor episode · observation ${station.observationTier ?? "UNKNOWN"} · ${station.hazardDecision ?? "Recovery or review pending"}.`
          : station.depthFresh
          ? `Generated from the latest valid ${station.dataSource === "simulator" ? "virtual-station" : "device"} reading.`
          : `Unresolved hazard; retained valid depth measured ${station.measurementAge ?? "at an unknown time"}. Latest sample is invalid or stale.`,
      }]
    : []);
}

export function MonitoringProvider({ children }: { children: ReactNode }) {
  const [selectedStationId, setSelectedStationId] = useState("");
  const [snapshot, setSnapshot] = useState<MonitoringSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [clock, setClock] = useState(0);
  const active = useRef(true);
  const inFlight = useRef(false);

  const refresh = useCallback(async (signal?:AbortSignal) => {
    if (inFlight.current) return;
    inFlight.current = true;
    try {
      const next = await accountRequest<MonitoringSnapshot>("monitoring/stations?history_limit=120", "GET", undefined, signal?AbortSignal.any([signal,AbortSignal.timeout(5000)]):AbortSignal.timeout(5000));
      if (active.current && !signal?.aborted) { setSnapshot(next); setError(""); }
    } catch (reason) {
      if (active.current && !signal?.aborted) setError(reason instanceof Error ? reason.message : "Monitoring data is unavailable.");
      throw reason;
    } finally {
      inFlight.current = false;
      if (active.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    active.current = true;
    setClock(Date.now());
    const stop=visiblePoll(refresh,3000,undefined,()=>setClock(Date.now()));
    const timer=window.setInterval(()=>{if(!document.hidden)setClock(Date.now());},1000);
    return ()=>{active.current=false;stop();window.clearInterval(timer);};
  }, [refresh]);

  const stations = useMemo(() => mergeStations(snapshot,clock,Boolean(error)), [snapshot,clock,error]);
  const sensorAlerts = useMemo(() => snapshot ? alertsFor(stations) : [], [snapshot, stations]);
  const dataMode: DataMode = !snapshot ? "no_data" : snapshot.stations.some(station => station.source === "simulator")
    ? "simulator" : snapshot.stations.some(station => station.source === "device" && station.source_trusted) ? "device"
      : snapshot.stations.some(station=>station.source==="unverified")?"unverified":"no_data";

  return <MonitoringContext.Provider value={{ selectedStationId, selectStation: setSelectedStationId, stations, sensorAlerts, snapshot, loading, error, dataMode, refresh:()=>refresh().catch(()=>undefined) }}>{snapshot?.service_health?.status==="degraded"&&<p role="status" className="subtle-note px-4 py-2">{snapshot.service_health.message}</p>}{children}</MonitoringContext.Provider>;
}

export function useMonitoring() {
  const context = useContext(MonitoringContext);
  if (!context) throw new Error("useMonitoring requires MonitoringProvider");
  return context;
}
