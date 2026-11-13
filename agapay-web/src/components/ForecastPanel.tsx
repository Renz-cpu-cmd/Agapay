"use client";
import Link from 'next/link';

import { useEffect, useState, type ReactNode } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { visiblePoll } from "@/lib/visible-poll";
import { accountRequest } from "@/lib/accounts";
import { forecastDepth, forecastInterval, forecastLabels, forecastTime, parsePrediction,parsePublishedPrediction, type ForecastStatus, type Prediction } from "@/lib/predictions";

export default function ForecastPanel({ stationId, title: heading = "Flood forecast", stationControl, sourceNote }: { stationId: string; title?: string; stationControl?: ReactNode; sourceNote?: ReactNode }) {
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
    const tick=()=>setClock(Date.now());tick();
    const timer = setInterval(() => {if(!document.hidden)tick();}, 1000);
    document.addEventListener("visibilitychange",tick);
    return () => {clearInterval(timer);document.removeEventListener("visibilitychange",tick);};
  }, []);
  useEffect(() => {
    let stopped = false;
    setData(null); setError("");
    async function poll(signal:AbortSignal) {
      setLoading(true);
      const started = Date.now();
      try {
        const raw=await accountRequest(`predictions/${encodeURIComponent(stationId)}?mode=${preview ? "preview" : "actual"}&scenario=${scenario}`,"GET",undefined,AbortSignal.any([signal,AbortSignal.timeout(5000)]));
        const next = preview?parsePrediction(raw):parsePublishedPrediction(raw);
        if (next.station_id !== stationId || (preview ? next.source !== "simulated" : next.source === "simulated")) throw new Error("The forecast source did not match the requested station or mode.");
        if (!stopped && !signal.aborted) {
          setData(next); setSampleAllowed(next.preview_allowed); setError(""); setClock(Date.now());
          setDeadline(next.valid_until ? started + Date.parse(next.valid_until) - Date.parse(next.checked_at) : 0);
        }
      } catch (e) {
        if (!stopped && !signal.aborted) { setData(null); setError(e instanceof Error ? e.message : "The forecast service is unavailable."); }
        if(!signal.aborted)throw e;
      } finally {
        if (!stopped) setLoading(false);
      }
    }
    const stop=visiblePoll(poll,30000);
    return () => { stopped = true; stop(); };
  }, [stationId, preview, scenario, refreshKey]);

  const current = data?.station_id === stationId && (preview ? data.source === "simulated" : data.source !== "simulated") ? data : null;
  const expired = current?.status === "available" && clock >= deadline;
  const available = current?.status === "available" && !expired;
  const title = error ? "Service unavailable" : expired ? "Forecast expired" : current ? forecastLabels[current.status] : "Checking forecast…";
  const reason = error || (expired ? "The forecast has expired. Refresh to check availability." : current?.reason);
  const points = available ? current.forecasts.map((p) => ({ label: `+${p.horizon_minutes}m`, value: p.water_depth_cm })) : [];

  return <section className="forecast-panel design-panel p-4 flex flex-col gap-3" aria-label={heading}>
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h2 className="font-ui font-bold text-xs tracking-widest uppercase text-slate-400">{heading}</h2>
      <span className={`font-data text-xs ${preview ? "text-amber-400" : "text-slate-500"}`}>{preview ? "PREVIEW" : "ADVISORY ONLY"}</span>
    </div>
    {stationControl}
    {sourceNote}
    <div className="flex items-center justify-between gap-3"><p className="text-xs font-bold text-slate-300" role="status">{title}</p><button onClick={() => setRefreshKey((n) => n + 1)} disabled={loading} className="text-xs text-sky-400 disabled:opacity-50">{loading ? "Checking…" : "Refresh"}</button></div>
    {available ? <div className="h-28"><ResponsiveContainer width="100%" height="100%"><LineChart data={points} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
      <CartesianGrid strokeDasharray="2 3" stroke="var(--design-line)"/><XAxis dataKey="label" tick={{ fill: "var(--adaptive-secondary, #64748b)", fontSize: 9 }} axisLine={false} tickLine={false}/><YAxis tick={{ fill: "var(--adaptive-secondary, #64748b)", fontSize: 9 }} axisLine={false} tickLine={false} width={40}/><Tooltip formatter={(v) => [`${forecastDepth(Number(v),current?.uncertainty?.display_resolution_cm)} cm`, preview ? "Sample" : "Forecast"]} contentStyle={{ background: "var(--adaptive-surface, #001637)", border: "1px solid var(--design-line)", borderRadius: 4, fontSize: 10 }}/><Line type="linear" dataKey="value" stroke="var(--adaptive-blue, #0ea5e9)" strokeWidth={1.8} dot={{ fill: "var(--adaptive-blue, #0ea5e9)", r: 3 }}/>
    </LineChart></ResponsiveContainer></div> : <div className="h-20 flex items-center justify-center border border-dashed border-slate-800 text-xs text-slate-500">Forecast unavailable</div>}
    <div className="grid grid-cols-3 gap-3">{[30, 60, 90].map((h, i) => <div key={h} className="flex flex-col gap-1"><span className="font-data text-xs text-slate-500">+{h} min</span><span className={`font-data font-bold text-sm ${available ? "text-sky-400" : "text-slate-500"}`}>{available ? `${forecastDepth(current.forecasts[i].water_depth_cm,current.uncertainty?.display_resolution_cm)} cm` : "—"}</span>{available && <span className="text-[10px] text-slate-500">{forecastTime(current.forecasts[i].target_at)} PHT</span>}{available&&!preview&&<span className="text-xs">{forecastInterval(current.forecasts[i].lower_depth_cm,current.forecasts[i].upper_depth_cm)}</span>}</div>)}</div>
    {available&&!preview&&current.uncertainty&&<p className="text-xs">{Math.round(current.uncertainty.nominal_coverage*100)}% nominal event interval · withheld event coverage {Math.round(current.uncertainty.withheld_event_coverage*100)}%. Coverage can fail under drift; this is local-depth uncertainty, not flood probability.</p>}
    {reason && <p className={`text-xs leading-relaxed ${error ? "text-red-400" : "text-slate-400"}`}>{reason}</p>}
    {current && <div className="text-[10px] text-slate-500 flex flex-col gap-1">
      <span>{preview ? "Preview input" : "Latest input"}: {forecastTime(current.input_last_recorded_at)} PHT</span>
      {available && <span>Generated: {forecastTime(current.generated_at)} PHT · Valid until: {forecastTime(current.valid_until)} PHT</span>}
      {current.model_version && <span>Model: {current.model_version}</span>}
      {current.forecast_id&&<><Link href={`/forecasts/${current.forecast_id}`}>Forecast ID: {current.forecast_id} · binding {current.deployment_version}</Link><span>Datum: {current.reference_datum} · cutoff {forecastTime(current.data_cutoff??null)} PHT</span><span>Configuration: {current.configuration_hash}</span></>}
    </div>}
    <p className="text-[10px] text-slate-500">Advisory only. Measured thresholds determine alert levels.</p>
    {preview && (sampleAllowed || preview) && <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-slate-800">
      <button className="text-xs text-sky-400" onClick={() => { setData(null); setPreview(!preview); }}>{preview ? "Return to actual status" : "Preview sample scenarios"}</button>
      {preview && <select aria-label="Forecast preview scenario" className="design-input max-w-full" value={scenario} onChange={(e) => { setData(null); setScenario(e.target.value as ForecastStatus); }}>{Object.entries(forecastLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>}
    </div>}
  </section>;
}
