"use client";

import { useMonitoring } from "@/context/MonitoringContext";

export default function SystemHealth() {
  const { stations, dataMode, snapshot, refresh, loading } = useMonitoring();
  const online = stations.filter((s) => s.isOnline).length;
  const offline = stations.length - online;

  return (
    <div className="design-page health-screen">
      <div className="design-controls"><span className="subtle-note">SOURCE · {dataMode === "simulator" ? "VIRTUAL STATION" : dataMode.replace("_", " ").toUpperCase()}{snapshot ? ` · OFFLINE AFTER ${snapshot.stale_after_seconds}s` : ""}</span><button className="design-button small ml-auto" onClick={() => void refresh()} disabled={loading}>{loading ? "REFRESHING…" : "REFRESH"}</button></div>
      {/* Summary */}
      <div className="card-grid grid-cols-3">
        {[
          { label: "Total Stations", value: stations.length, color: "#0ea5e9" },
          { label: "Online", value: online, color: "#00e83a" },
          { label: "Offline", value: offline, color: offline > 0 ? "#ff0000" : "#64748b" },
        ].map(({ label, value, color }) => (
          <div key={label} className="p-4 flex flex-col gap-1" style={{ background: "#00112e", border: "1px solid #002967", borderRadius: "4px" }}>
            <span className="font-ui text-xs font-600 tracking-widest uppercase" style={{ color: "#8190a4", letterSpacing: "0.12em" }}>{label}</span>
            <span className="font-data text-4xl font-bold" style={{ color }}>{value}</span>
          </div>
        ))}
      </div>

      {/* Offline alert */}
      {offline > 0 && (
        <div className="px-4 py-3 flex items-center gap-3" style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.3)", borderRadius: "4px" }}>
          <span className="font-ui font-700 text-xs" style={{ color: "#ff0000" }}>⚠ {offline} station(s) offline — data may be stale</span>
        </div>
      )}

      {/* Station table */}
      <div style={{ background: "#00112e", border: "1px solid #002967", borderRadius: "4px", overflow: "hidden" }}>
        <table className="w-full">
          <thead>
            <tr style={{ borderBottom: "1px solid #002967" }}>
              {["Station","Location","Connection","Water Level Sensor","Rain Gauge","Last Ping","Firmware"].map(h => (
                <th key={h} className="text-left px-4 py-2.5 font-ui font-700 text-xs tracking-wide" style={{ color: "#8190a4", letterSpacing: "0.1em" }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {stations.map((st) => (
              <tr key={st.id} style={{ borderBottom: "1px solid #000916" }}>
                <td className="px-4 py-3">
                  <p className="font-data font-bold text-xs" style={{ color: "#94a3b8" }}>{st.id}</p>
                  <p className="text-xs mt-0.5" style={{ color: "#64748b" }}>{st.name.split(" Station")[0]}</p>
                </td>
                <td className="px-4 py-3 text-xs" style={{ color: "#64748b" }}>{st.location}</td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-1.5">
                    <div className="w-2 h-2 rounded-full" style={{ background: st.isOnline ? "#00e83a" : "#ff0000" }}/>
                    <span className="font-ui font-700 text-xs" style={{ color: st.isOnline ? "#00e83a" : "#ff0000" }}>
                      {st.isOnline ? "Online" : "Offline"}
                    </span>
                  </div>
                </td>
                <td className="px-4 py-3">
                  <span className="font-data text-xs" style={{ color: st.sensorValid ? "#00e83a" : "#f5df00" }}>
                    {st.sensorValid ? "✓ Valid" : "⚠ Invalid"}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className="font-data text-xs" style={{ color: st.isOnline ? "#00e83a" : "#6b7280" }}>
                    {st.isOnline ? "✓ Active" : "— Unknown"}
                  </span>
                </td>
                <td className="px-4 py-3 font-data text-xs" style={{ color: st.isOnline ? "#64748b" : "#ff0000" }}>
                  {st.lastPing}
                </td>
                <td className="px-4 py-3 font-data text-xs" style={{ color: "#8190a4" }}>{st.firmware}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Offline detail cards */}
      {stations.filter(s => !s.isOnline).map((st) => (
        <div key={st.id} className="p-4 flex flex-col gap-2" style={{ background: "#310c00", border: "1px solid #c41b00", borderRadius: "4px" }}>
          <div className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full" style={{ background: "#ff0000" }}/>
            <span className="font-ui font-700 text-sm" style={{ color: "#ff0000" }}>🔴 STATION OFFLINE</span>
            <span className="font-data text-xs" style={{ color: "#8190a4" }}>{st.id}</span>
          </div>
          <div className="grid grid-cols-3 gap-4 mt-1">
            {[
              ["Last Communication", st.lastPing],
              ["Last Known Water Level", `${st.waterLevel} cm`],
              ["Last Known Alert", st.status],
            ].map(([k, v]) => (
              <div key={k} className="flex flex-col gap-0.5">
                <span className="text-xs" style={{ color: "#8190a4" }}>{k}</span>
                <span className="font-data font-bold text-xs" style={{ color: "#94a3b8" }}>{v}</span>
              </div>
            ))}
          </div>
          <p className="font-ui font-700 text-xs mt-1" style={{ color: "#f97316" }}>DATA IS STALE</p>
        </div>
      ))}

      {/* Sensor error detail */}
      {stations.filter(s => s.isOnline && !s.sensorValid).map((st) => (
        <div key={st.id} className="p-4 flex flex-col gap-2" style={{ background: "rgba(234,179,8,0.06)", border: "1px solid rgba(234,179,8,0.25)", borderRadius: "4px" }}>
          <div className="flex items-center gap-2">
            <span className="font-ui font-700 text-sm" style={{ color: "#f5df00" }}>⚠ SENSOR ERROR</span>
            <span className="font-data text-xs" style={{ color: "#8190a4" }}>{st.id}</span>
          </div>
          <p className="text-xs" style={{ color: "#94a3b8" }}>
            Water-level measurement unavailable. Last valid reading: {st.waterLevel} cm · Data state: INVALID
          </p>
          <p className="text-xs" style={{ color: "#64748b" }}>
            Previous alert state retained. Do not interpret as NORMAL.
          </p>
        </div>
      ))}
    </div>
  );
}
