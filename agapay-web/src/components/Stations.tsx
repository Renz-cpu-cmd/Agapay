"use client";

import { useState } from "react";
import ForecastPanel from "./ForecastPanel";
import { FigmaIcon } from "./DesignUI";
import { useRouter } from "next/navigation";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer,
  AreaChart, Area
} from "recharts";
import { useMonitoring } from "@/context/MonitoringContext";
import { tierColor, tierBg, trendLabel, type Station } from "../data/mockData";

function TierBadge({ tier, label }: { tier: string; label?: string }) {
  const color = tierColor[tier as keyof typeof tierColor] ?? "#6b7280";
  return (
    <span
      className="font-ui font-700 text-xs px-2 py-0.5 rounded-sm"
      style={{ background: `${color}18`, color, border: `1px solid ${color}35`, letterSpacing: "0.08em" }}
    >
      {label ?? tier}
    </span>
  );
}

function StationDetail({ station, onBack }: { station: Station; onBack: () => void }) {
  const [timeRange, setTimeRange] = useState<"LIVE" | "1H" | "6H" | "24H">("LIVE");
  const dataSlice = { LIVE: 8, "1H": 12, "6H": 18, "24H": 24 }[timeRange];
  const chartData = station.waterHistory.slice(-dataSlice);
  const levelPct = Math.min(100, (station.waterLevel / 130) * 100);

  return (
    <div className="design-page station-detail-screen">
      {/* Back + header */}
      <div className="flex items-center gap-3">
        <button
          onClick={onBack}
          className="flex items-center gap-1.5 font-ui text-xs transition-colors"
          style={{ color: "#8190a4" }}
          onMouseEnter={(e) => (e.currentTarget.style.color = "#0ea5e9")}
          onMouseLeave={(e) => (e.currentTarget.style.color = "#8190a4")}
        >
          ← Back
        </button>
        <span style={{ color: "#002967" }}>|</span>
        <span className="font-data text-xs" style={{ color: "#64748b" }}>{station.id}</span>
      </div>

      <div className="card-grid grid-cols-3">
        {/* Station info */}
        <div className="col-span-2 card-stack">
          {/* Header card */}
          <div className="p-4 flex flex-col gap-3" style={{ background: "#00112e", border: "1px solid #002967", borderRadius: "4px" }}>
            <div className="flex items-start justify-between">
              <div>
                <h2 className="font-ui font-700 text-base" style={{ color: "#ffffff" }}>{station.name}</h2>
                <p className="text-xs mt-0.5" style={{ color: "#8190a4" }}>{station.location}</p>
              </div>
              <TierBadge tier={station.status} />
            </div>
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full" style={{ background: station.isOnline ? "#00e83a" : "#ff0000" }} />
              <span className="font-data text-xs" style={{ color: station.isOnline ? "#00e83a" : "#ff0000" }}>
                {station.isOnline ? "ONLINE" : "OFFLINE"}
              </span>
              <span className="font-data text-xs" style={{ color: "#64748b" }}>· Last ping: {station.lastPing}</span>
            </div>

            {/* Offline warning */}
            {!station.isOnline && (
              <div className="p-3" style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.25)", borderRadius: "4px" }}>
                <p className="font-ui font-700 text-xs" style={{ color: "#ff0000" }}>🔴 STATION OFFLINE</p>
                <p className="text-xs mt-1" style={{ color: "#94a3b8" }}>
                  Last communication: {station.lastPing} · Last known level: {station.waterLevel} cm
                </p>
                <p className="font-ui font-700 text-xs mt-1" style={{ color: "#f97316" }}>DATA IS STALE</p>
              </div>
            )}

            {/* Sensor error */}
            {!station.sensorValid && station.isOnline && (
              <div className="p-3" style={{ background: "rgba(234,179,8,0.08)", border: "1px solid rgba(234,179,8,0.25)", borderRadius: "4px" }}>
                <p className="font-ui font-700 text-xs" style={{ color: "#f5df00" }}>⚠ SENSOR ERROR</p>
                <p className="text-xs mt-1" style={{ color: "#94a3b8" }}>
                  Water-level measurement unavailable. Last valid: {station.waterLevel} cm — Data state: INVALID
                </p>
              </div>
            )}
          </div>

          {/* Water level + chart */}
          <div className="p-4 flex flex-col gap-3" style={{ background: "#00112e", border: "1px solid #002967", borderRadius: "4px" }}>
            <div className="flex items-center justify-between">
              <span className="font-ui font-700 text-xs tracking-widest uppercase" style={{ color: "#8190a4", letterSpacing: "0.12em" }}>
                Water Depth — Live
              </span>
              <div className="flex gap-1.5">
                {(["LIVE","1H","6H","24H"] as const).map((r) => (
                  <button
                    key={r}
                    onClick={() => setTimeRange(r)}
                    className="font-data text-xs px-2 py-0.5 transition-all"
                    style={{
                      background: timeRange === r ? "#0ea5e9" : "transparent",
                      color: timeRange === r ? "#fff" : "#8190a4",
                      borderRadius: "3px",
                      border: `1px solid ${timeRange === r ? "#0ea5e9" : "#002967"}`,
                    }}
                  >
                    {r}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex items-end gap-6">
              <div>
                <span className="font-data text-4xl font-bold" style={{ color: tierColor[station.status] }}>
                  {station.waterLevel}
                </span>
                <span className="font-data text-xl ml-1" style={{ color: "#8190a4" }}>cm</span>
              </div>
              <span className="font-ui font-700 text-sm mb-1" style={{ color: tierColor[station.status] }}>
                {trendLabel[station.trend]}
              </span>
            </div>

            {/* Gauge bar */}
            <div className="relative h-2 rounded-sm overflow-hidden" style={{ background: "#002052" }}>
              <div
                className="h-full transition-all"
                style={{ width: `${levelPct}%`, background: tierColor[station.status], boxShadow: `0 0 8px ${tierColor[station.status]}60` }}
              />
              {/* Threshold markers */}
              {[
                { val: station.thresholds.advisory, color: "#f5df00" },
                { val: station.thresholds.warning, color: "#f97316" },
                { val: station.thresholds.evacuate, color: "#ff0000" },
              ].map(({ val, color }) => (
                <div
                  key={val}
                  className="absolute top-0 bottom-0 w-px"
                  style={{ left: `${(val / 130) * 100}%`, background: color }}
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
                  <CartesianGrid stroke="#002967" strokeDasharray="3 3" vertical={false}/>
                  <XAxis dataKey="time" tick={{ fill: "#64748b", fontSize: 9, fontFamily: "Inter" }} interval={Math.ceil(chartData.length / 6)} tickLine={false} axisLine={false}/>
                  <YAxis tick={{ fill: "#64748b", fontSize: 9, fontFamily: "Inter" }} tickLine={false} axisLine={false} width={30} domain={["auto","auto"]}/>
                  <ReferenceLine y={station.thresholds.evacuate} stroke="#ff0000" strokeDasharray="4 2" strokeWidth={1} label={{ value: "EVACUATE", position: "insideTopRight", fill: "#ff0000", fontSize: 8, fontFamily: "Inter" }}/>
                  <ReferenceLine y={station.thresholds.warning} stroke="#f97316" strokeDasharray="4 2" strokeWidth={1}/>
                  <ReferenceLine y={station.thresholds.advisory} stroke="#f5df00" strokeDasharray="4 2" strokeWidth={1}/>
                  <Tooltip
                    contentStyle={{ background: "#00112e", border: "1px solid #002967", borderRadius: "4px", fontSize: 10, fontFamily: "Inter", color: "#ffffff" }}
                    itemStyle={{ color: tierColor[station.status] }}
                  />
                  <Area type="monotone" dataKey="level" stroke={tierColor[station.status]} strokeWidth={1.8} fill="url(#wlGrad)" dot={false}/>
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          <ForecastPanel key={station.id} stationId={station.id} />
        </div>

        {/* Right column */}
        <div className="card-stack">
          {/* Rainfall */}
          <div className="p-4 flex flex-col gap-2" style={{ background: "#00112e", border: "1px solid #002967", borderRadius: "4px" }}>
            <span className="font-ui font-700 text-xs tracking-widest uppercase" style={{ color: "#8190a4", letterSpacing: "0.12em" }}>Rainfall</span>
            <span className="font-data text-3xl font-bold" style={{ color: "#0ea5e9" }}>{station.rainfall}</span>
            <span className="font-data text-sm" style={{ color: "#8190a4" }}>mm this reporting interval</span>
          </div>

          {/* Thresholds */}
          <div className="p-4 flex flex-col gap-3" style={{ background: "#00112e", border: "1px solid #002967", borderRadius: "4px" }}>
            <span className="font-ui font-700 text-xs tracking-widest uppercase" style={{ color: "#8190a4", letterSpacing: "0.12em" }}>Alert Thresholds</span>
            {[
              { label: "Advisory", val: station.thresholds.advisory, color: "#f5df00" },
              { label: "Warning", val: station.thresholds.warning, color: "#f97316" },
              { label: "Evacuate", val: station.thresholds.evacuate, color: "#ff0000" },
            ].map(({ label, val, color }) => (
              <div key={label} className="flex items-center justify-between py-1.5" style={{ borderBottom: "1px solid #001637" }}>
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full" style={{ background: color }} />
                  <span className="font-ui text-xs" style={{ color: "#64748b" }}>{label}</span>
                </div>
                <span className="font-data font-bold text-sm" style={{ color }}>{val}.0 cm</span>
              </div>
            ))}
          </div>

          {/* Sensor status */}
          <div className="p-4 flex flex-col gap-3" style={{ background: "#00112e", border: "1px solid #002967", borderRadius: "4px" }}>
            <span className="font-ui font-700 text-xs tracking-widest uppercase" style={{ color: "#8190a4", letterSpacing: "0.12em" }}>Sensor Status</span>
            {[
              { label: "Water Level Sensor", ok: station.sensorValid },
              { label: "Rain Gauge", ok: station.isOnline },
              { label: "Connection", ok: station.isOnline },
            ].map(({ label, ok }) => (
              <div key={label} className="flex items-center justify-between">
                <span className="text-xs" style={{ color: "#64748b" }}>{label}</span>
                <span className="font-data text-xs font-bold" style={{ color: ok ? "#00e83a" : "#ff0000" }}>
                  {ok ? "✓ Valid" : "✗ Error"}
                </span>
              </div>
            ))}
            <div className="flex items-center justify-between">
              <span className="text-xs" style={{ color: "#64748b" }}>Firmware</span>
              <span className="font-data text-xs" style={{ color: "#8190a4" }}>{station.firmware}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function Stations({ initialStationId }: { initialStationId?: string }) {
  const router = useRouter();
  const { stations, dataMode, loading } = useMonitoring();
  const selected = initialStationId;

  if (selected) {
    const st = stations.find((s) => s.id === selected);
    if (st) return <StationDetail station={st} onBack={() => router.push("/stations")} />;
  }

  return <div className="design-page stations-screen"><p className="subtle-note">{stations.length} STATIONS · {stations.filter(s => s.isOnline).length} ONLINE · {loading ? "CONNECTING" : dataMode === "simulator" ? "VIRTUAL STATION" : dataMode.replace("_", " ").toUpperCase()}</p>
    <div className="stations-grid">{stations.map(st => <button key={st.id} onClick={() => router.push(`/stations/${encodeURIComponent(st.id)}`)} className="station-card design-panel" style={{borderColor:st.status === "EVACUATE" ? "#db0000" : undefined}}>
      <header><div><h2>{st.name}</h2><small>{st.id}</small></div><span className="design-badge" style={{color:tierColor[st.status],background:tierColor[st.status]+"25"}}>{st.status}</span></header>
      <div className="station-connection"><span style={{color:st.isOnline?"#00ff24":"#ff0000"}}>• {st.isOnline?"ONLINE":"OFFLINE"}</span><small>· {st.lastPing}{!st.isOnline&&" · Last known reading"}</small></div>
      <dl className="station-values"><div><dt>Water Level</dt><dd className="depth" style={{color:tierColor[st.status]}}>{st.waterLevel} cm</dd></div><div><dt>Rainfall</dt><dd>{st.rainfall} mm</dd></div></dl>
      <p className="station-trend">{trendLabel[st.trend]}</p><div className="water-bar"><div style={{width:Math.min(100,st.waterLevel/130*100)+"%",background:tierColor[st.status]}}/></div>
    </button>)}</div>
  </div>;
}
export { StationDetail };
