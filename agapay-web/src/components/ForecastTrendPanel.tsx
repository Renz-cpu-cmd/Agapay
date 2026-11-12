"use client";

import Link from "next/link";
import OperationalStateLabel from "./OperationalState";
import { stationMeasurement, measurementLabel, measurementText, measurementNote } from "@/lib/measurements";
import type { ReactNode } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useHybridProjection } from "@/context/HybridProjectionContext";
import { useMonitoring } from "@/context/MonitoringContext";
import { ageLabel, monitoringSourceLabel, monitoringStationForDisplay } from "@/lib/monitoring";
import PublishedForecastPanel from './ForecastPanel';

export default function ForecastTrendPanel(props:{stationId:string;stationControl?:ReactNode;showDetails?:boolean;experiment?:boolean}) {
  return props.experiment?<PrivateExperiment {...props}/>:<PublishedTrend {...props}/>;
}
function PublishedTrend({stationId,stationControl}:{stationId:string;stationControl?:ReactNode}) {
  const {stations}=useMonitoring();
  const depth=stations.find(row=>row.id===stationId)?.depth;
  return <PublishedForecastPanel stationId={stationId} stationControl={stationControl} title="Water-depth forecast" sourceNote={<div className="forecast-trend-source"><p>{depth?.value!=null?`${measurementLabel(depth)} · ${measurementText(depth,1,'cm')} · ${depth.reason}`:depth?.reason??'No measurement received'}</p>{depth&&<details className="station-evidence"><summary>Input quality and timestamp</summary><p>{measurementNote(depth)}</p></details>}</div>}/>;
}
function PrivateExperiment({stationId,stationControl,showDetails=true}:{stationId:string;stationControl?:ReactNode;showDetails?:boolean}) {
  const {data,active,available,expired,error,config,clock}=useHybridProjection(stationId);
  const {snapshot,error:monitoringError}=useMonitoring();
  const station=snapshot?.stations.find(s=>s.station_id===stationId);
  const view=station&&snapshot?monitoringStationForDisplay(station,snapshot.checked_at,snapshot.stale_after_seconds,clock,Boolean(monitoringError)):null;
  const depth=view ? stationMeasurement(view,"depth") : null;
  const delta=available?data!.points[2].depth_cm-data!.adjusted!.depth_cm:0;
  const trend=delta>.001?"Rising":delta<-.001?"Falling":"Stable";
  const points=available?[{label:"Modeled now",value:data!.adjusted!.depth_cm},...data!.points.map(p=>({label:`+${p.horizon_minutes}m`,value:p.depth_cm}))]:[];
  const source=available?(data!.mode==="historical_context"?`Historical context · manual start ${data!.initial_depth_cm!.toFixed(1)} cm`:data!.rain_snapshot?.data_source==="simulated_rain_gauge"?"Synthetic test feed":data!.rain_snapshot?.ml_ready?"Live gauge history":"Live rain · historical ML context"):"Experimental projection";
  const status=expired?"Forecast expired":error?"Forecast service unavailable":!active?"Forecast not configured":!available&&data?.status==="unavailable"?"Live inputs unavailable":!available?"Checking forecast…":`${trend} · ${delta>=0?"+":""}${delta.toFixed(0)} cm over 90 minutes`;
  const updated=available?new Date(data!.checked_at).toLocaleTimeString("en-PH",{timeZone:"Asia/Manila",hour:"2-digit",minute:"2-digit",second:"2-digit"}):null;

  return <section className="forecast-panel forecast-trend design-panel" aria-label="Experimental projection trend">
    <header className="forecast-trend-heading"><h2>Experimental projection</h2><span>{available?trend:"Pending"}</span></header>
    {stationControl}
    <OperationalStateLabel state="exercise" detail="Private experiment · not a published forecast"/>
    <div className="forecast-trend-current"><span>{`${depth ? measurementLabel(depth) : "No valid reading"} · Water depth`}</span><strong>{depth ? measurementText(depth,1,"cm") : "—"}</strong><small>{depth ? measurementNote(depth) : "No measurement received"}{view ? ` · ${ageLabel(view.depth_age_seconds,view.connection_status)}` : ""}{view?.hazard_state==="unresolved"?" · Hazard unresolved":""}</small></div>
    {station&&<p className="forecast-trend-source">{monitoringSourceLabel(station)} · latest sample {station.sensor_quality??"unknown"}</p>}
    <p className="forecast-trend-status" role="status">{status}</p>
    {available&&<p className="forecast-trend-source">Modeled now: {data!.adjusted!.depth_cm.toFixed(0)} cm · {config.depthSource==="sensor"?"registry-verified physical starting depth":"manual starting depth"} {data!.initial_depth_cm!.toFixed(1)} cm</p>}
    {available?<div className="forecast-trend-chart"><ResponsiveContainer width="100%" height="100%"><LineChart data={points} margin={{top:8,right:10,bottom:0,left:0}}><CartesianGrid stroke="var(--design-line)" strokeDasharray="3 3"/><XAxis dataKey="label" tick={{fill:"var(--adaptive-secondary)",fontSize:10}} axisLine={false} tickLine={false}/><YAxis domain={[(min:number)=>Math.max(0,min-.5),(max:number)=>max+.5]} tickFormatter={value=>Number(value).toFixed(1)} tick={{fill:"var(--adaptive-secondary)",fontSize:10}} width={42} axisLine={false} tickLine={false}/><Tooltip formatter={value=>[`${Number(value).toFixed(0)} cm`,"Projected depth"]} contentStyle={{background:"var(--design-panel)",border:"1px solid var(--design-line)",fontSize:11}}/><Line dataKey="value" stroke="var(--adaptive-blue)" strokeWidth={2} strokeDasharray="5 3" dot={{r:3}} isAnimationActive={false}/></LineChart></ResponsiveContainer></div>:<div className="forecast-trend-empty">{active?"Waiting for valid forecast inputs.":"Set up forecasting in ML Configuration."}</div>}
    <div className="forecast-trend-horizons">{[30,60,90].map((h,i)=><div key={h}><span>+{h} minutes</span><strong>{available?`${data!.points[i].depth_cm.toFixed(0)} cm`:"—"}</strong></div>)}</div>
    <p className="forecast-trend-source">{source}{available&&config.depthSource==="manual"&&data!.mode!=="historical_context"?" · manual start":""}</p>
    <footer><span>{updated?`Updated ${updated} PHT`:"Awaiting forecast"}</span>{showDetails&&<Link href="/ml-configuration">ML details →</Link>}</footer>
    <p className="forecast-trend-note">Experimental projection · basin calibration pending; projected depths are not validated for flood warnings.</p>
  </section>;
}
