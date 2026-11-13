"use client";

import {useEffect,useState} from "react";
import Link from "next/link";
import {Bar,BarChart,CartesianGrid,ResponsiveContainer,Tooltip,XAxis,YAxis} from "recharts";
import {accountRequest} from "@/lib/accounts";
import {visiblePoll} from '@/lib/visible-poll';
import {selectRainActivity,type RainSnapshot} from "@/lib/rainfall-activity";
import {rainPresentation,type RainConfiguration,type RainProduct} from "@/lib/rain-presentation";

const time=(at:string|number)=>new Date(at).toLocaleTimeString("en-PH",{timeZone:"Asia/Manila",hour:"2-digit",minute:"2-digit"});

export default function RainfallActivityPanel({stationId,variant="dashboard",configuration,physicalValidation}:{stationId:string;variant?:"dashboard"|"analytics";configuration?:RainConfiguration;physicalValidation?:string|null}) {
  const config={rainSource:'physical_rain_gauge'};
  const [clock,setClock]=useState(0);
  useEffect(()=>{const tick=()=>setClock(Date.now());tick();const timer=setInterval(tick,1000);return()=>clearInterval(timer);},[]);
  const [feed,setFeed]=useState<RainSnapshot|null>(null);
  const [state,setState]=useState("Connecting");
  useEffect(()=>{
    let stopped=false;
    setFeed(null);setState("Connecting");
    async function poll(signal:AbortSignal){
      try{
        const response=await accountRequest<{workspace:string;rain_activity:RainSnapshot|null}>(`rain-activity/${encodeURIComponent(stationId)}`,"GET",undefined,AbortSignal.any([signal,AbortSignal.timeout(3000)]));
        const snapshot=response.rain_activity;
        if(stopped||signal.aborted)return;
        if(response.workspace!=='observations_only'||!snapshot)throw Error('Rain observations unavailable');
        if(snapshot.station_id!==stationId || snapshot.data_source!==config.rainSource || !Array.isArray(snapshot.completed_hours))throw Error("Rainfall source did not match");
        setFeed(snapshot);setState(snapshot.connected?"Connected":"Offline");
      }catch(error){if(!stopped&&!signal.aborted){setFeed(null);setState("Unavailable");}throw error;}
    }
    const stop=visiblePoll(poll,3000);return()=>{stopped=true;stop();};
  },[stationId,config.rainSource]);
  const archived:[]=[];
  const view=selectRainActivity(feed,stationId,config.rainSource,clock,state==="Unavailable",archived);
  const simulated=config.rainSource==="simulated_rain_gauge";
  const bars=view.chart.map(row=>({...row,label:row.partial?"Now":time(row.at),complete:row.partial?null:row.amount,ongoing:row.partial?row.amount:null}));
  const hasChart=view.chart.some(row=>row.amount!==null);
  const currentHour=new Date(clock).toLocaleTimeString("en-PH",{timeZone:"Asia/Manila",hour:"2-digit",minute:"2-digit"});

  // A8: coverage, calibration and origin of the figure come from structured metadata only.
  const rain=rainPresentation(feed?.current_hour_product as RainProduct,configuration,physicalValidation);
  return <section className={`rainfall-activity design-panel ${variant==="analytics"?"rainfall-analytics":""}`} aria-label="Rainfall activity">
    <header><h2>{rain.title}</h2>{rain.badge&&<span className="rain-badge" data-testid="rain-badge">{rain.badge}</span>}<span className={view.fresh?"rain-connected":""}>{view.fresh?(simulated?"VIRTUAL":"Connected"):state==="Connecting"?"Connecting":"Offline"}</span></header>
    <div className="rainfall-amount"><span>{"Received rain this hour"}</span><strong>{view.current===null?"—":view.current.toFixed(3)}<small>{view.current===null?"":` ${rain.amountSuffix}`}</small></strong><p>{view.current===null?"Waiting for current gauge readings.":`Incomplete hour · ${currentHour} PHT · received tips only`}</p><p className="rain-caveat" data-testid="rain-caveat">{[rain.tips,rain.coverage].filter(Boolean).join(" · ")}. {rain.caveat}</p></div>
    <p className="subtle-note">Interval {feed?.current_hour_product?.interval_start??"—"} to {feed?.current_hour_product?.interval_end??"—"} · {feed?.current_hour_product?.coverage??"Coverage unknown"} · {config.rainSource} · config {feed?.calibration_version??"unknown"}</p><div className="rainfall-chart-heading"><h3>{view.chartSource==="archive"?"Archived rainfall context":"Rainfall trend"}</h3><span>{view.chartSource==="archive"?"HISTORICAL CONTEXT":simulated?"VIRTUAL OBSERVATIONS":"Hourly amounts · mm"}</span></div>
    <div className="rainfall-chart">{hasChart?<ResponsiveContainer width="100%" height="100%"><BarChart data={bars} margin={{top:8,right:0,bottom:0,left:0}}><CartesianGrid stroke="var(--design-line)" strokeDasharray="3 3" vertical={false}/><XAxis dataKey="label" interval="preserveStartEnd" minTickGap={35} tick={{fill:"var(--adaptive-secondary)",fontSize:9}} axisLine={false} tickLine={false}/><YAxis width={32} tickFormatter={value=>Number(value).toFixed(1)} tick={{fill:"var(--adaptive-secondary)",fontSize:9}} axisLine={false} tickLine={false}/><Tooltip labelFormatter={(_,payload)=>{const row=payload?.[0]?.payload;return row?`${new Date(row.at).toLocaleString("en-PH",{timeZone:"Asia/Manila"})} PHT${row.partial?" · ongoing hour":" · completed hour"}`:"";}} formatter={value=>[`${Number(value).toFixed(3)} mm`,"Rainfall"]} contentStyle={{background:"var(--design-panel)",border:"1px solid var(--design-line)",fontSize:10}}/><Bar dataKey="complete" name="Completed hour" fill="var(--adaptive-blue)" radius={[3,3,0,0]} stackId="rain"/><Bar dataKey="ongoing" name="Ongoing hour" fill="var(--adaptive-orange)" radius={[3,3,0,0]} stackId="rain"/></BarChart></ResponsiveContainer>:<div className="rainfall-empty"><span aria-hidden="true">☂</span><strong>No rainfall history available</strong><p>Rainfall activity will appear when the gauge is connected.</p></div>}</div>
    <p className="rainfall-context">{view.fresh?"Completed hours are blue; the ongoing hour is orange. Missing intervals stay unknown.":"No rainfall amount is assumed while the gauge is unavailable."}</p>
    <dl className="rainfall-feed"><div><dt>Gauge</dt><dd>{view.fresh?(simulated?"Virtual gauge feed":"Physical rain gauge"):"Not connected"}</dd></div><div><dt>Last gauge update</dt><dd>{view.received===null?"—":time(view.received)+" PHT"}</dd></div></dl>
    <footer><span>{stationId}</span><Link href="/ml-configuration">Rainfall details →</Link></footer>
  </section>;
}
