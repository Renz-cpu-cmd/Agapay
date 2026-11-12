"use client";
import { useEffect, useRef, useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useMonitoring } from "@/context/MonitoringContext";
import { accountRequest } from "@/lib/accounts";
import { historySeries, localInputToUtc, reportCsv, type HistoryReport } from "@/lib/history-report";
import RainfallActivityPanel from "./RainfallActivityPanel";
import StationComparison from "./StationComparison";

const number=(value:number|null)=>value===null?"—":value.toFixed(3);
const reportTime=(value:string,timeZone:string)=>new Date(value).toLocaleString("en-PH",{timeZone,year:"numeric",month:"short",day:"numeric",hour:"2-digit",minute:"2-digit",second:"2-digit"});
const colors=["var(--adaptive-blue)","var(--adaptive-orange)","var(--adaptive-success)","var(--adaptive-danger)"];
export default function Analytics(){
  const {stations}=useMonitoring();
  const [station,setStation]=useState("All Stations"),[period,setPeriod]=useState("1 Hour");
  const [zone,setZone]=useState<"UTC"|"Asia/Manila">("Asia/Manila"),[bucket,setBucket]=useState(60);
  const [start,setStart]=useState(""),[end,setEnd]=useState(""),[eventId,setEventId]=useState("");
  const [report,setReport]=useState<HistoryReport|null>(null),[error,setError]=useState(""),[busy,setBusy]=useState(false);
  const generation=useRef(0),mounted=useRef(true),initialLoad=useRef(false);
  const hours:Record<string,number>={"1 Hour":1,"6 Hours":6,"24 Hours":24,"7 Days":168};
  useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;++generation.current;};},[]);
  function changed(action:()=>void){++generation.current;setReport(null);setError("");setBusy(false);action();}
  async function load(){
    const request=++generation.current;setBusy(true);setError("");setReport(null);
    try{
      const query=new URLSearchParams({timezone:zone,bucket_seconds:String(bucket)});
      if(station!=="All Stations")query.set("station_id",station);
      if(eventId)query.set("event_id",eventId);
      if(!eventId||period==="Custom"){
        const finish=new Date();
        query.set("start_at",period==="Custom"?localInputToUtc(start,zone):new Date(finish.getTime()-hours[period]*3600000).toISOString());
        query.set("end_at",period==="Custom"?localInputToUtc(end,zone):finish.toISOString());
      }
      const next=await accountRequest<HistoryReport>(`monitoring/history?${query}`,"GET",undefined,AbortSignal.timeout(15000));
      if(mounted.current&&request===generation.current)setReport(next);
    }catch(reason){if(mounted.current&&request===generation.current)setError(reason instanceof Error?reason.message:"Report unavailable; no partial data exported.");}
    finally{if(mounted.current&&request===generation.current)setBusy(false);}
  }
  useEffect(()=>{if(stations.length&&!initialLoad.current){initialLoad.current=true;void load();}},[stations.length]);
  function download(){
    if(!report)return;
    const url=URL.createObjectURL(new Blob([reportCsv(report)],{type:"text/csv;charset=utf-8;"}));
    const anchor=document.createElement("a");anchor.href=url;anchor.download=`agapay-water-depth-${report.scope.event_id?`event-${report.scope.event_id}`:"range"}.csv`;anchor.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  const series=report?historySeries(report):[];
  const rainStation=stations.find(s=>s.id===station)??stations[0];
  return <div className="design-page analytics-screen">
    <section className="design-panel p-4 report-filters"><h2>MEASURED WATER-DEPTH HISTORY</h2><p className="subtle-note">Choose a database time range or sensor episode. Chart and CSV share exactly the loaded scope; monitoring's short live window is not used as a daily report.</p>
      <div className="design-controls">
        <label>Station<select aria-label="Station" className="design-input" value={station} onChange={e=>changed(()=>setStation(e.target.value))}><option>All Stations</option>{stations.map(item=><option key={item.id} value={item.id}>{item.name} · {item.id}</option>)}</select></label>
        <label>Period<select aria-label="Period" className="design-input" value={period} onChange={e=>changed(()=>setPeriod(e.target.value))}>{(eventId?["Event","Custom"]:[...Object.keys(hours),"Custom"]).map(value=><option key={value} value={value}>{value==="Event"?"Whole episode":value}</option>)}</select></label>
        <label>Timezone<select aria-label="Report timezone" className="design-input" value={zone} onChange={e=>changed(()=>setZone(e.target.value as typeof zone))}><option>Asia/Manila</option><option>UTC</option></select></label>
        <label>Mean bucket<select aria-label="Aggregation interval" className="design-input" value={bucket} onChange={e=>changed(()=>setBucket(Number(e.target.value)))}>{[30,60,300,900,3600].map(value=><option key={value} value={value}>{value} seconds</option>)}</select></label>
        <label>Sensor event ID (optional)<input aria-label="Sensor event ID" className="design-input" type="number" min={1} value={eventId} onChange={e=>changed(()=>{setEventId(e.target.value);setPeriod(e.target.value?"Event":"1 Hour");})}/></label>
      </div>
      {period==="Custom"&&<div className="design-controls"><label>From ({zone})<input aria-label="Report start" className="design-input" type="datetime-local" value={start} onChange={e=>changed(()=>setStart(e.target.value))}/></label><label>To ({zone})<input aria-label="Report end" className="design-input" type="datetime-local" value={end} onChange={e=>changed(()=>setEnd(e.target.value))}/></label></div>}
      <button className="design-button primary" onClick={()=>void load()} disabled={busy||(period==="Custom"&&(!start||!end))}>{busy?"Loading database scope…":"Load report"}</button>
      {error&&<p role="alert">{error}</p>}
    </section>
    {!report&&<section className="design-panel chart-card"><h2>WATER DEPTH OVER TIME</h2><div className="chart-canvas design-empty">{busy?"Loading measured history…":error?"History unavailable; no substitute readings are plotted.":"No report loaded. Select a report scope to view measured history."}</div></section>}
    {report&&<>
      <section className="design-panel chart-card"><h2>BUCKET MEAN DEPTH (CM) · GAPS REMAIN UNKNOWN</h2>
        {report.stations.every(item=>item.valid_count===0)&&<p className="subtle-note">No qualifying depth measurements in this selected range. No line is invented.</p>}
        <div className="chart-canvas"><ResponsiveContainer width="100%" height="100%"><LineChart data={series}><CartesianGrid stroke="var(--design-line)"/><XAxis dataKey="at" type="number" domain={[Date.parse(report.scope.start_at),Date.parse(report.scope.end_at)]} tickFormatter={value=>new Date(value).toLocaleString("en-PH",{timeZone:report.scope.timezone,hour:"2-digit",minute:"2-digit",month:"short",day:"numeric"})}/><YAxis unit=" cm"/><Tooltip labelFormatter={value=>new Date(Number(value)).toLocaleString("en-PH",{timeZone:report.scope.timezone})}/><Legend/>{report.stations.map((item,index)=><Line key={item.station_id} dataKey={item.station_id} name={item.station_id} stroke={colors[index%colors.length]} connectNulls={false} dot={false} isAnimationActive={false}/>)}</LineChart></ResponsiveContainer></div>
      </section>
    </>}
    <div className="analytics-rainfall">
      <p className="subtle-note">Rainfall journal · {rainStation?.id??"No station selected"}. This independent hourly window is separate from the selected depth report and its CSV.</p>
      {rainStation?<RainfallActivityPanel stationId={rainStation.id} variant="analytics"/>:<section className="design-panel chart-card"><h2>RAINFALL (MM)</h2><div className="chart-canvas design-empty">No rainfall station available.</div></section>}
    </div>
    <StationComparison stations={stations}/>
    <section className="design-panel report-card event-report"><h2>FLOOD EVENT / SELECTED DEPTH REPORT</h2>
      {!report?<p className="design-empty">{busy?"Loading selected scope…":"No report loaded. Choose a time range or sensor event above."}</p>:<>
        <dl className="report-grid"><div><dt>From</dt><dd><time dateTime={report.scope.start_at} title={report.scope.start_local}>{reportTime(report.scope.start_at,report.scope.timezone)}</time></dd></div><div><dt>To</dt><dd><time dateTime={report.scope.end_at} title={report.scope.end_local}>{reportTime(report.scope.end_at,report.scope.timezone)}</time></dd></div><div><dt>Timezone</dt><dd>{report.scope.timezone}</dd></div><div><dt>Sensor event</dt><dd>{report.scope.event_id??"No event selected"}</dd></div><div><dt>Stations</dt><dd>{report.scope.station_ids.join(", ")||"None"}</dd></div><div><dt>Event status</dt><dd>{report.scope.event_status??"Time-range report"}</dd></div></dl>
        {report.stations.map(item=><article key={item.station_id}><h3>{item.station_name} · {item.station_id}</h3><p>Minimum {number(item.minimum_depth_cm)} cm · Maximum {number(item.maximum_depth_cm)} cm · Mean {number(item.mean_depth_cm)} cm</p><p className="subtle-note">{item.valid_count}/{item.sample_count} qualifying samples · {item.covered_buckets}/{item.expected_buckets} covered buckets</p><details><summary>Quality, source and coverage</summary><p>{item.invalid_count} invalid · {item.review_count} review · {item.unverified_count} unverified</p><p className="subtle-note">Sources: {JSON.stringify(item.source_details)}</p></details></article>)}
        <details><summary>Exact report scope and exclusions</summary><p>{report.scope.aggregation} · {report.scope.boundary}</p><p>{report.scope.timestamp_basis} · {report.scope.unsynchronized_rows_excluded} receipt-only rows excluded · {report.scope.rows_scanned} measured rows examined</p><p>{report.scope.coverage_basis}. {report.scope.rainfall_scope}.</p></details>
        <button className="design-button primary" onClick={download}>DOWNLOAD SELECTED SCOPE CSV</button>
      </>}
    </section>
  </div>;
}
