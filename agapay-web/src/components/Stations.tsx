"use client";

import { useState } from "react";
import ForecastPanel from "./ForecastPanel";
import StationWorkspace from "./StationWorkspace";
import StationStatusFacts from "./StationStatusFacts";
import {measurementText,measurementNote,measurementLabel,measurementPercent} from "@/lib/measurements";
import {measuredSeries} from "@/lib/staff-workspaces";
import { FigmaIcon } from "./DesignUI";
import { useRouter } from "next/navigation";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer,
  AreaChart, Area
} from "recharts";
import { useMonitoring } from "@/context/MonitoringContext";
import { tierColor, tierTextColor, tierBg, trendLabel, type Station } from "../data/mockData";

function TierBadge({ tier, label }: { tier: string; label?: string }) {
  const color = tierTextColor[tier as keyof typeof tierTextColor] ?? "var(--adaptive-muted, #6b7280)";
  return (
    <span
      className="font-ui font-700 text-xs px-2 py-0.5 rounded-sm"
      style={{ background: `color-mix(in srgb, ${color} 9%, transparent)`, color, border: `1px solid color-mix(in srgb, ${color} 21%, transparent)`, letterSpacing: "0.08em" }}
    >
      {label ?? tier}
    </span>
  );
}

function StationDetail({ station, onBack }: { station: Station; onBack: () => void }) {
  const [timeRange, setTimeRange] = useState<"LIVE" | "1H" | "6H" | "24H">("LIVE");
  const dataSlice = { LIVE: 8, "1H": 12, "6H": 18, "24H": 24 }[timeRange];
  const chartData = measuredSeries(station.waterHistory.slice(-dataSlice),30);
  const observationColor = station.depth.state==="current"?tierTextColor[station.observationTier??"UNKNOWN"]:"var(--adaptive-text)";
  const levelPct = station.depth.value == null ? 0 : Math.min(100, station.depth.value / (station.thresholds.evacuate * 1.2) * 100);

  return (
    <div className="design-page station-detail-screen">
      {/* Back + header */}
      <div className="flex items-center gap-3">
        <button
          onClick={onBack}
          className="flex items-center gap-1.5 font-ui text-xs transition-colors"
          style={{ color: "var(--adaptive-muted, #8190a4)" }}
          onMouseEnter={(e) => (e.currentTarget.style.color = "var(--adaptive-blue, #0ea5e9)")}
          onMouseLeave={(e) => (e.currentTarget.style.color = "var(--adaptive-muted, #8190a4)")}
        >
          ← Back
        </button>
        <span style={{ color: "var(--adaptive-border, #002967)" }}>|</span>
        <span className="font-data text-xs" style={{ color: "var(--adaptive-secondary, #64748b)" }}>{station.id}</span>
      </div>

      <div className="card-grid grid-cols-3">
        {/* Station info */}
        <div className="col-span-2 card-stack">
          {/* Header card */}
          <div className="p-4 flex flex-col gap-3" style={{ background: "var(--adaptive-surface, #00112e)", border: "1px solid var(--design-line)", borderRadius: "4px" }}>
            <div className="flex items-start justify-between">
              <div>
                <h2 className="font-ui font-700 text-base" style={{ color: "var(--adaptive-text, #ffffff)" }}>{station.name}</h2>
                <p className="text-xs mt-0.5" style={{ color: "var(--adaptive-muted, #8190a4)" }}>{station.location}</p>
              </div>
              <TierBadge tier={station.status} label={station.activeHazardTier?`Episode · ${station.activeHazardTier}`:`Observation · ${station.depth.state==="current"?station.observationTier??"UNKNOWN":"UNKNOWN"}`}/>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full" style={{ background: station.isOnline ? "var(--adaptive-success, #00e83a)" : "var(--adaptive-danger, #ff0000)" }} />
              <span className="font-data text-xs" style={{ color: station.isOnline ? "var(--adaptive-success, #00e83a)" : "var(--adaptive-danger, #ff0000)" }}>
                {station.connectionStatus?.toUpperCase()??"UNKNOWN"}
              </span>
              <span className="font-data text-xs" style={{ color: "var(--adaptive-secondary, #64748b)" }}>· Last ping: {station.lastPing}</span>
            </div>

            {/* Offline warning */}
            {!station.isOnline && (
              <div className="p-3" style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.25)", borderRadius: "4px" }}>
                <p className="font-ui font-700 text-xs" style={{ color: "var(--adaptive-danger, #ff0000)" }}>STATION {station.connectionStatus?.toUpperCase()??"UNKNOWN"}</p>
                <p className="text-xs mt-1" style={{ color: "var(--adaptive-muted, #94a3b8)" }}>
                  Last communication: {station.lastPing} · Last known depth: {measurementText(station.depth)} cm
                </p>
                <p className="font-ui font-700 text-xs mt-1" style={{ color: "var(--adaptive-orange, #f97316)" }}>{station.depth.value==null?"NO VALID READING":"LAST KNOWN DATA"}</p>
              </div>
            )}

            {/* Sensor error */}
            {!station.sensorValid && station.isOnline && (
              <div className="p-3" style={{ background: "rgba(234,179,8,0.08)", border: "1px solid rgba(234,179,8,0.25)", borderRadius: "4px" }}>
                <p className="font-ui font-700 text-xs" style={{ color: "var(--adaptive-warning, #f5df00)" }}>⚠ SENSOR ERROR</p>
                <p className="text-xs mt-1" style={{ color: "var(--adaptive-muted, #94a3b8)" }}>
                  Water-depth measurement unavailable. Last valid: {measurementText(station.depth)} cm — Data state: INVALID
                </p>
              </div>
            )}
          </div>

          {/* Water level + chart */}
          <div className="p-4 flex flex-col gap-3" style={{ background: "var(--adaptive-surface, #00112e)", border: "1px solid var(--design-line)", borderRadius: "4px" }}>
            <div className="flex items-center justify-between">
              <span className="font-ui font-700 text-xs tracking-widest uppercase" style={{ color: "var(--adaptive-muted, #8190a4)", letterSpacing: "0.12em" }}>
                Water Depth — Observations
              </span>
              <div className="flex gap-1.5">
                {(["LIVE","1H","6H","24H"] as const).map((r) => (
                  <button
                    key={r}
                    onClick={() => setTimeRange(r)} disabled={r !== "LIVE"} title={r !== "LIVE" ? "Open Analytics for a persisted time-range report" : "Recent samples"}
                    className="font-data text-xs px-2 py-0.5 transition-all"
                    style={{
                      background: timeRange === r ? "var(--adaptive-blue, #0ea5e9)" : "transparent",
                      color: timeRange === r ? "var(--adaptive-action-foreground, #000)" : "var(--adaptive-muted, #8190a4)",
                      borderRadius: "3px",
                      border: `1px solid ${timeRange === r ? "var(--adaptive-blue, #0ea5e9)" : "var(--adaptive-border, #002967)"}`,
                    }}
                  >
                    {r}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex items-end gap-6">
              <div>
                <span className="font-data text-4xl font-bold" style={{ color: observationColor }}>
                  {measurementText(station.depth)}
                </span>
                <span className="font-data text-xl ml-1" style={{ color: "var(--adaptive-muted, #8190a4)" }}>cm</span>
              </div>
              <span className="font-ui font-700 text-sm mb-1" style={{ color: observationColor }}>
                {trendLabel[station.trend]}
              </span>
            </div>

            {/* Gauge bar */}
            <div className="relative h-2 rounded-sm overflow-hidden" style={{ background: "var(--adaptive-border, #002052)" }}>
              <div
                className="h-full transition-all"
                style={{ width: `${levelPct}%`, background: tierColor[station.status], boxShadow: `0 0 8px ${tierColor[station.status]}60` }}
              />
              {/* Threshold markers */}
              {[
                { val: station.thresholds.advisory, color: "var(--adaptive-warning, #f5df00)" },
                { val: station.thresholds.warning, color: "var(--adaptive-orange, #f97316)" },
                { val: station.thresholds.evacuate, color: "var(--adaptive-danger, #ff0000)" },
              ].map(({ val, color }) => (
                <div
                  key={val}
                  className="absolute top-0 bottom-0 w-px"
                  style={{ left: `${(val / (station.thresholds.evacuate * 1.2)) * 100}%`, background: color }}
                />
              ))}
            </div>

            <div style={{ height: 160 }}>
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData} margin={{ top: 4, right: 4, bottom: 4, left: 0 }}>
                  <defs>
                    <linearGradient id="wlGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={tierColor[station.status]} stopOpacity={0.2}/>
                      <stop offset="95%" stopColor={tierColor[station.status]} stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="var(--adaptive-border, #002967)" strokeDasharray="3 3" vertical={false}/>
                  <XAxis dataKey="at" type="number" domain={["dataMin","dataMax"]} tickFormatter={at=>new Date(at).toLocaleTimeString("en-PH",{hour:"2-digit",minute:"2-digit",timeZone:"Asia/Manila"})} tick={{ fill: "var(--adaptive-secondary, #64748b)", fontSize: 9, fontFamily: "Inter" }} interval={Math.ceil(chartData.length / 6)} tickLine={false} axisLine={false}/>
                  <YAxis tick={{ fill: "var(--adaptive-secondary, #64748b)", fontSize: 9, fontFamily: "Inter" }} tickLine={false} axisLine={false} width={30} domain={["auto","auto"]}/>
                  <ReferenceLine y={station.thresholds.evacuate} stroke="var(--adaptive-danger, #ff0000)" strokeDasharray="4 2" strokeWidth={1} label={{ value: "EVACUATE", position: "insideTopRight", fill: "var(--adaptive-danger, #ff0000)", fontSize: 8, fontFamily: "Inter" }}/>
                  <ReferenceLine y={station.thresholds.warning} stroke="var(--adaptive-orange, #f97316)" strokeDasharray="4 2" strokeWidth={1}/>
                  <ReferenceLine y={station.thresholds.advisory} stroke="var(--adaptive-warning, #f5df00)" strokeDasharray="4 2" strokeWidth={1}/>
                  <Tooltip
                    contentStyle={{ background: "var(--adaptive-surface, #00112e)", border: "1px solid var(--design-line)", borderRadius: "4px", fontSize: 10, fontFamily: "Inter", color: "var(--adaptive-text, #ffffff)" }}
                    itemStyle={{ color: tierTextColor[station.status] }}
                  />
                  <Area connectNulls={false} type="linear" dataKey="level" stroke={tierColor[station.status]} strokeWidth={1.8} fill="url(#wlGrad)" dot={false}/>
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          <ForecastPanel key={station.id} stationId={station.id} />
        </div>

        {/* Right column */}
        <div className="card-stack">
          {/* Rainfall */}
          <div className="p-4 flex flex-col gap-2" style={{ background: "var(--adaptive-surface, #00112e)", border: "1px solid var(--design-line)", borderRadius: "4px" }}>
            <span className="font-ui font-700 text-xs tracking-widest uppercase" style={{ color: "var(--adaptive-muted, #8190a4)", letterSpacing: "0.12em" }}>Rainfall</span>
            <span className="font-data text-3xl font-bold" style={{ color: "var(--adaptive-blue, #0ea5e9)" }}>{measurementText(station.rain,3)}</span>
            <span className="font-data text-sm" style={{ color: "var(--adaptive-muted, #8190a4)" }}>mm · received journal interval</span>
          </div>

          {/* Thresholds */}
          <div className="p-4 flex flex-col gap-3" style={{ background: "var(--adaptive-surface, #00112e)", border: "1px solid var(--design-line)", borderRadius: "4px" }}>
            <span className="font-ui font-700 text-xs tracking-widest uppercase" style={{ color: "var(--adaptive-muted, #8190a4)", letterSpacing: "0.12em" }}>Alert Thresholds</span>
            {[
              { label: "Advisory", val: station.thresholds.advisory, color: "var(--adaptive-warning, #f5df00)" },
              { label: "Warning", val: station.thresholds.warning, color: "var(--adaptive-orange, #f97316)" },
              { label: "Evacuate", val: station.thresholds.evacuate, color: "var(--adaptive-danger, #ff0000)" },
            ].map(({ label, val, color }) => (
              <div key={label} className="flex items-center justify-between py-1.5" style={{ borderBottom: "1px solid var(--design-line)" }}>
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full" style={{ background: color }} />
                  <span className="font-ui text-xs" style={{ color: "var(--adaptive-secondary, #64748b)" }}>{label}</span>
                </div>
                <span className="font-data font-bold text-sm" style={{ color }}>{val.toFixed(1)} cm</span>
              </div>
            ))}
          </div>

          {/* Sensor status */}
          <div className="p-4 flex flex-col gap-3" style={{ background: "var(--adaptive-surface, #00112e)", border: "1px solid var(--design-line)", borderRadius: "4px" }}>
            <span className="font-ui font-700 text-xs tracking-widest uppercase" style={{ color: "var(--adaptive-muted, #8190a4)", letterSpacing: "0.12em" }}>Sensor Status</span>
            {[
              { label: "Water Depth Sensor", ok: station.channelHealth?.water_sensor.state },
              { label: "Rain Gauge", ok: station.channelHealth?.rain_counter.state },
              { label: "Connection", ok: station.channelHealth?.device_heartbeat.state },
            ].map(({ label, ok }) => (
              <div key={label} className="flex items-center justify-between">
                <span className="text-xs" style={{ color: "var(--adaptive-secondary, #64748b)" }}>{label}</span>
                <span className="font-data text-xs font-bold" style={{ color: ok === "healthy" ? "var(--adaptive-success, #00e83a)" : "var(--adaptive-danger, #ff0000)" }}>
                  {ok ?? "unknown"}
                </span>
              </div>
            ))}
            <div className="flex items-center justify-between">
              <span className="text-xs" style={{ color: "var(--adaptive-secondary, #64748b)" }}>Firmware</span>
              <span className="font-data text-xs" style={{ color: "var(--adaptive-muted, #8190a4)" }}>{station.firmware}</span>
            </div>
          </div>
        </div>
      </div>
      <details className="design-panel p-4"><summary>Device configuration, maintenance and evidence</summary><StationWorkspace station={station} onBack={onBack}/></details>
    </div>
  );
}

export default function Stations({ initialStationId }: { initialStationId?: string }) {
  const router = useRouter();
  const { stations, dataMode, loading, error, refresh } = useMonitoring();
  const selected = initialStationId;

  if (loading) return <div className="design-page stations-screen"><p className="subtle-note" role="status">Connecting to station readings…</p></div>;

  if (selected) {
    const st = stations.find((s) => s.id === selected);
    if (st) return <StationDetail station={st} onBack={() => router.push("/stations")} />;
    return <div className="design-page stations-screen"><h1>Station evidence unavailable</h1><p>{error?"Monitoring could not be checked. The requested station cannot currently be confirmed.":"The requested station is not present in the monitoring registry."}</p><button className="design-button" onClick={()=>void refresh()}>Refresh station registry</button><button className="design-button" onClick={()=>router.push("/stations")}>Back to stations</button></div>;
  }

  return <div className="design-page stations-screen"><p className="subtle-note">{stations.length} STATIONS · {stations.filter(s => s.isOnline).length} ONLINE · {loading ? "CONNECTING" : dataMode === "simulator" ? "VIRTUAL STATION" : dataMode.replace("_", " ").toUpperCase()}</p>
    {!stations.length&&<p role="status">No valid reading · No stations are available. An administrator must provision and commission a station before observations can be shown.</p>}
    <div className="stations-grid">{stations.map(st => <article key={st.id} className="station-card design-panel" style={{borderColor:st.status === "EVACUATE" ? "var(--adaptive-danger, #db0000)" : undefined}}>
      <header><div><h2>{st.name}</h2><small>{st.id}</small></div><span className="design-badge" style={{color:tierTextColor[st.status],background:tierColor[st.status]+"25"}}>{st.activeHazardTier?`Sensor episode: ${st.activeHazardTier}`:`Observation tier: ${st.depth.state==="current"?st.observationTier??st.status:"UNKNOWN"}`}</span></header>
      <div className="station-connection"><span style={{color:!st.isOnline&&st.connectionStatus!=="offline"?"var(--state-unknown)":st.isOnline?"var(--adaptive-success, #00ff24)":"var(--adaptive-danger, #ff0000)"}}>• {st.connectionStatus?.replaceAll("_"," ").toUpperCase()??"UNKNOWN"}</span><small>· {st.lastPing}{!st.isOnline&&st.depth.value!==null&&" · Last known reading"}</small></div>
      <dl className="station-values"><div><dt>{`${measurementLabel(st.depth)} · Water depth`}</dt><dd className="depth" style={{color:st.depth.state==="current"?tierTextColor[st.observationTier??"UNKNOWN"]:"var(--adaptive-text)"}}>{measurementText(st.depth,1,"cm")}</dd></div><div><dt>Rainfall · received this UTC hour</dt><dd>{measurementText(st.rain, 3,"mm")}</dd></div></dl>
      <StationStatusFacts station={st} compact/>
      <p className="subtle-note">{st.sourceTrusted&&st.depthSourceTrusted?"Authenticated registered device":"Unregistered source"}{st.depth.value!==null?` · Measured ${st.measurementAge??"at an unknown time"}`:""}</p>
      <p className="station-trend">{st.depth.state === "current" ? trendLabel[st.trend] : st.depth.reason}</p><div className="water-bar"><div style={{width:measurementPercent(st.depth, st.thresholds.evacuate*1.2),background:st.depth.state==="current"?tierColor[st.observationTier??"UNKNOWN"]:"var(--design-muted)"}}/></div>
      <details className="station-evidence"><summary>Measurement evidence</summary><StationStatusFacts station={st}/><p className="subtle-note">Depth: {measurementNote(st.depth)}</p><p className="subtle-note">Rain: {measurementNote(st.rain)}</p><p className="subtle-note">{st.riseRate==null?"Rate unavailable":`${st.riseRate.toFixed(1)} cm/min`} · {st.trendReason??"Insufficient timing/coverage"}</p></details>
      <button className="design-button station-open" onClick={()=>router.push(`/stations/${encodeURIComponent(st.id)}`)}>View station<span className="sr-only"> · {st.name}</span></button>
    </article>)}</div>
  </div>;
}
export { StationDetail };
