"use client";

import type { ReactNode } from "react";
import { useHybridProjection, type Basin } from "@/context/HybridProjectionContext";

const parameterLabels: Record<keyof Basin, string> = {
  contributing_area_m2: "Collection area (m²)", basin_surface_area_m2: "Basin surface (m²)",
  runoff_coefficient: "Runoff coefficient", outflow_m3_per_hour: "Outflow (m³/hour)", maximum_depth_cm: "Capacity depth (cm)",
};

export default function HybridForecastPanel({stationId, stationControl}: {stationId: string; stationControl?: ReactNode}) {
  const {config,active,data,error,expired,available,configure,start,stop}=useHybridProjection(stationId);
  const {mode,depthSource,rainSource,initial,context,basin,basis,confirmed}=config;
  const status=error || (expired?"Projection expired. Waiting for fresh inputs.":data?.status==="unavailable"?data.reason:active?(available?"Projection running. Return to the preview above to see updates.":"Connecting to projection inputs…"):"Ready to configure. Changing an input stops the current projection.");

  return <div className="ml-settings" aria-label="Hybrid ML water-depth projection settings">
    <section className="ml-settings-section">
      <header><span className="ml-step">01</span><div><h3>Data sources</h3><p>Choose the station and observations used to initialize the model.</p></div></header>
      <div className="hybrid-inputs">
        {stationControl}
        <label className="hybrid-field">Rainfall mode<select className="design-input" aria-label="Hybrid rainfall mode" value={mode} onChange={e=>configure({mode:e.target.value,...(e.target.value==="historical_context"?{depthSource:"manual"}:{})})}><option value="historical_context">Historical rainfall experiment</option><option value="live">Live rain gauge · automatic updates</option></select></label>
        <label className="hybrid-field">Starting depth source<select className="design-input" aria-label="Projection depth source" value={depthSource} onChange={e=>configure({depthSource:e.target.value})}><option value="manual">Manual configured depth</option>{mode==="live"&&<option value="sensor">Fresh ESP32 measurement</option>}</select></label>
        {depthSource==="manual"&&<label className="hybrid-field">Manual depth (cm)<input className="design-input" aria-label="Manual projection depth (cm)" type="number" min="0" step="any" value={initial} onChange={e=>configure({initial:e.target.value})}/></label>}
        {mode==="live"&&<label className="hybrid-field">Rain event source<select className="design-input" aria-label="Rain event source" value={rainSource} onChange={e=>configure({rainSource:e.target.value})}><option value="physical_rain_gauge">Physical gauge · station calibration</option><option value="simulated_rain_gauge">Synthetic test feed</option></select></label>}
      </div>
    </section>
    <section className="ml-settings-section">
      <header><span className="ml-step">02</span><div><h3>Basin parameters</h3><p>Record the physical dimensions and how each value was obtained.</p></div></header>
      <div className="ml-basin-grid">{(Object.keys(basin) as (keyof Basin)[]).map(key=><div className="ml-parameter" key={key}><label className="hybrid-field">{parameterLabels[key]}<input className="design-input" aria-label={parameterLabels[key]} type="number" step="any" value={Number.isFinite(basin[key])?basin[key]:""} onChange={e=>configure({basin:{...basin,[key]:e.target.value===""?NaN:Number(e.target.value)}})}/></label><label className="hybrid-field">Value basis<select className="design-input" aria-label={`${parameterLabels[key]} basis`} value={basis[key]} onChange={e=>configure({basis:{...basis,[key]:e.target.value}})}>{["assumed","estimated","measured"].map(value=><option key={value}>{value}</option>)}</select></label></div>)}</div>
    </section>
    <section className="ml-settings-section">
      <header><span className="ml-step">03</span><div><h3>Rainfall context</h3><p>The saved model uses 24 completed hourly rainfall observations.</p></div></header>
      <label className="hybrid-field ml-context-field">Archived 24-hour origin (UTC)<input className="design-input" aria-label="Hybrid archived origin (UTC)" type="datetime-local" min="2025-01-01T00:00" max="2025-12-31T23:00" step="3600" value={context} onChange={e=>configure({context:e.target.value})}/></label>
      <p className="ml-muted">Archived ERA5 context is used until 24 consecutive live hours are complete. New tips update basin inflow separately from the model’s hourly input window.</p>
    </section>
    <footer className="ml-settings-footer">
      <label className="ml-confirm"><input type="checkbox" checked={confirmed} onChange={e=>configure({confirmed:e.target.checked})}/><span>I am using a controlled test basin or proxy with the parameters above.</span></label>
      <div className="ml-settings-actions"><p role="status" className={error?"ml-error":"ml-muted"}>{status}</p><div><button className="design-button primary" disabled={!confirmed || initial.trim()==="" || !Number.isFinite(Number(initial)) || active} onClick={start}>{active?"Projection running":mode==="live"?"Start live projection":"Start experiment"}</button>{active&&<button className="design-button danger" onClick={stop}>Stop projection</button>}</div></div>
    </footer>
  </div>;
}
