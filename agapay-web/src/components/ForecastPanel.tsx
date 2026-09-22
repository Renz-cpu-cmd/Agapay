"use client";

import { useEffect, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { accountRequest } from "@/lib/accounts";
import { forecastLabels, forecastTime, parsePrediction, type ForecastStatus, type Prediction } from "@/lib/predictions";

export default function ForecastPanel({ stationId }: { stationId: string }) {
  const [preview, setPreview] = useState(false);
  const [scenario, setScenario] = useState<ForecastStatus>("available");
  const [sampleAllowed, setSampleAllowed] = useState(false);
  const [data, setData] = useState<Prediction | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [deadline, setDeadline] = useState(0);
  const [clock, setClock] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => setClock(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    setData(null); setError("");
    async function poll() {
      setLoading(true);
      const started = Date.now();
      try {
        const next = parsePrediction(await accountRequest(`predictions/${encodeURIComponent(stationId)}?mode=${preview ? "preview" : "actual"}&scenario=${scenario}`));
        if (next.station_id !== stationId || (preview ? next.source !== "simulated" : next.source === "simulated")) throw new Error("The forecast source did not match the requested station or mode.");
        if (!stopped) {
          setData(next); setSampleAllowed(next.preview_allowed); setError(""); setClock(Date.now());
          setDeadline(next.valid_until ? started + Date.parse(next.valid_until) - Date.parse(next.checked_at) : 0);
        }
      } catch (e) {
        if (!stopped) { setData(null); setError(e instanceof Error ? e.message : "The forecast service is unavailable."); }
      } finally {
        if (!stopped) { setLoading(false); timer = setTimeout(poll, 30000); }
      }
    }
    void poll();
    return () => { stopped = true; clearTimeout(timer); };
  }, [stationId, preview, scenario, refreshKey]);

  const current = data?.station_id === stationId && (preview ? data.source === "simulated" : data.source !== "simulated") ? data : null;
  const expired = current?.status === "available" && clock >= deadline;
  const available = current?.status === "available" && !expired;
  const title = error ? "Service unavailable" : expired ? "Forecast expired" : current ? forecastLabels[current.status] : "Checking forecast…";
  const reason = error || (expired ? "The forecast has expired. Refresh to check availability." : current?.reason);
  const points = available ? current.forecasts.map((p) => ({ label: `+${p.horizon_minutes}m`, value: p.water_depth_cm })) : [];

  return <section className="p-4 flex flex-col gap-3" aria-label="Flood forecast" style={{ background: "#00112e", border: "1px solid #002967", borderRadius: 4 }}>
    <div className="flex flex-wrap items-center justify-between gap-2">
      <span className="font-ui font-bold text-xs tracking-widest uppercase text-slate-400">Flood forecast</span>
      <span className={`font-data text-xs ${preview ? "text-amber-400" : "text-slate-500"}`}>{preview ? "SIMULATED PREVIEW" : "ADVISORY ONLY"}</span>
    </div>
    <div className="flex items-center justify-between gap-3"><p className="text-xs font-bold text-slate-300" role="status">{title}</p><button onClick={() => setRefreshKey((n) => n + 1)} disabled={loading} className="text-xs text-sky-400 disabled:opacity-50">{loading ? "Checking…" : "Refresh"}</button></div>
    {available ? <div className="h-28"><ResponsiveContainer width="100%" height="100%"><LineChart data={points} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
      <CartesianGrid strokeDasharray="2 3" stroke="#001637"/><XAxis dataKey="label" tick={{ fill: "#64748b", fontSize: 9 }} axisLine={false} tickLine={false}/><YAxis tick={{ fill: "#64748b", fontSize: 9 }} axisLine={false} tickLine={false} width={40}/><Tooltip formatter={(v) => [`${v} cm`, preview ? "Sample" : "Forecast"]} contentStyle={{ background: "#001637", border: "1px solid #002967", borderRadius: 4, fontSize: 10 }}/><Line type="linear" dataKey="value" stroke="#0ea5e9" strokeWidth={1.8} dot={{ fill: "#0ea5e9", r: 3 }}/>
    </LineChart></ResponsiveContainer></div> : <div className="h-20 flex items-center justify-center border border-dashed border-slate-800 text-xs text-slate-500">Forecast unavailable</div>}
    <div className="grid grid-cols-3 gap-3">{[30, 60, 90].map((h, i) => <div key={h} className="flex flex-col gap-1"><span className="font-data text-xs text-slate-500">+{h} min</span><span className={`font-data font-bold text-sm ${available ? "text-sky-400" : "text-slate-500"}`}>{available ? `${current.forecasts[i].water_depth_cm!.toFixed(1)} cm` : "—"}</span>{available && <span className="text-[10px] text-slate-500">{forecastTime(current.forecasts[i].target_at)} PHT</span>}</div>)}</div>
    {reason && <p className={`text-xs leading-relaxed ${error ? "text-red-400" : "text-slate-400"}`}>{reason}</p>}
    {current && <div className="text-[10px] text-slate-500 flex flex-col gap-1">
      <span>{preview ? "Synthetic input" : "Latest input"}: {forecastTime(current.input_last_recorded_at)} PHT</span>
      {available && <span>Generated: {forecastTime(current.generated_at)} PHT · Valid until: {forecastTime(current.valid_until)} PHT</span>}
      {current.model_version && <span>Model: {current.model_version}</span>}
    </div>}
    <p className="text-[10px] text-slate-500">Advisory only. Measured thresholds determine alert levels.</p>
    {(sampleAllowed || preview) && <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-slate-800">
      <button className="text-xs text-sky-400" onClick={() => { setData(null); setPreview(!preview); }}>{preview ? "Return to actual status" : "Preview sample scenarios"}</button>
      {preview && <select aria-label="Forecast preview scenario" className="max-w-full text-xs bg-slate-950 text-amber-300 border border-slate-700 rounded p-1.5" value={scenario} onChange={(e) => { setData(null); setScenario(e.target.value as ForecastStatus); }}>{Object.entries(forecastLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>}
    </div>}
  </section>;
}
