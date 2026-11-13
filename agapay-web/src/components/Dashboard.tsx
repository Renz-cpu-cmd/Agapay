"use client";
import {useState} from "react";
import {LineChart,Line,XAxis,YAxis,CartesianGrid,Tooltip,ResponsiveContainer} from "recharts";
import {useMonitoring} from "@/context/MonitoringContext";
import {useSos} from "@/context/SosContext";
import {useAlertResource} from "@/hooks/useAlertResource";
import {useEvidenceClock} from "@/hooks/useEvidenceClock";
import {tierColor,tierTextColor,trendLabel} from "@/data/mockData";
import {measurementText,measurementNote} from "@/lib/measurements";
import {measuredSeries,readIsCurrent,type CommandQueue} from "@/lib/staff-workspaces";
import StationMap from "./StationMap";
import CommunityAlertThresholds from "./CommunityAlertThresholds";
import ForecastTrendPanel from "./ForecastTrendPanel";
import RainfallActivityPanel from "./RainfallActivityPanel";
import IncidentWorkspace from "./IncidentWorkspace";

export default function Dashboard({onViewStation}:{onViewStation:(id:string)=>void}) {
  const {stations,selectedStationId,selectStation,snapshot,error}=useMonitoring();
  const {page:sosPage,error:sosError}=useSos();
  const [review,setReview]=useState(false);
  const now=useEvidenceClock();
  const queue=useAlertResource<CommandQueue>("alerts/command-queue?scope=operational&limit=20&offset=0");
  const legacy=useAlertResource<CommandQueue>("alerts/command-queue?scope=unverified&limit=20&offset=0");
  const station=stations.find(row=>row.id===selectedStationId)??stations[0];
  const highest=stations.filter(row=>row.depth.state==="current"&&row.depth.value!==null).sort((a,b)=>b.depth.value!-a.depth.value!)[0];
  const currentCount=stations.filter(row=>row.depth.state==="current").length;
  const activeAlerts=[...(queue.data?.items??[]),...(legacy.data?.items??[])].sort((a,b)=>["EVACUATE","WARNING","ADVISORY"].indexOf(a.severity)-["EVACUATE","WARNING","ADVISORY"].indexOf(b.severity)||a.triggered_at.localeCompare(b.triggered_at));
  const total=queue.data&&legacy.data?queue.data.counts.operational+queue.data.counts.unverified:null;
  const stats=[
    {title:"Monitoring stations",value:stations.length,sub:`${stations.filter(s=>s.isOnline).length} online · ${stations.filter(s=>s.administrativeStatus==="maintenance").length} maintenance`,color:"var(--adaptive-blue, #7db3ff)"},
    {title:"Active alerts",value:total??"—",sub:queue.error||legacy.error?"Current count unavailable":"Recorded sensor episodes",color:"var(--adaptive-orange, #ff7500)"},
    {title:"Active SOS",value:sosPage?sosPage.counts.ACTIVE:"—",sub:sosError?"Status unavailable":!sosPage?"Connecting…":"Test environment · "+(sosPage?.counts.ACTIVE?"Needs response":"No active requests"),color:"var(--adaptive-danger, #ff0000)"},
    {title:"Highest depth",value:highest?measurementText(highest.depth,1,"cm"):"—",sub:highest?`${highest.id} · ${currentCount}/${stations.length} current`:`${currentCount}/${stations.length} current readings`,color:highest?tierTextColor[highest.observationTier??"UNKNOWN"]:"var(--design-muted)"},
  ];
  const data=station?measuredSeries(station.waterHistory,snapshot?.stale_after_seconds??30):[];
  const tick=(at:number)=>new Date(at).toLocaleTimeString("en-PH",{hour:"2-digit",minute:"2-digit",timeZone:"Asia/Manila"});
  return <div className="dashboard-screen">
    <div className="dashboard-stats">{stats.map(row=><section className="dashboard-stat" key={row.title}><h2>{row.title}</h2><strong style={{color:row.color}}>{row.value}</strong><p>{row.sub}</p></section>)}</div>
    <div className="dashboard-body"><div className="dashboard-left">
      <StationMap onViewStation={onViewStation} selectedStationId={station?.id} onSelectStation={selectStation}/>
      <div className="dashboard-analysis">
        <section className="dashboard-chart design-panel" aria-label="Water depth chart"><div className="chart-heading"><h2>Water Depth{station?` - ${station.id}`:""}</h2><span style={{color:station?.depth.value==null?"var(--design-muted)":tierTextColor[station?.observationTier??"UNKNOWN"]}}>{station?.depth.value!=null?`${measurementText(station.depth,1,"cm")} · ${station.depth.state==="current"?trendLabel[station.trend]:"Last known / unconfirmed"}`:"No valid reading"}</span></div>
          <div style={{height:200}}>{data.length?<ResponsiveContainer width="100%" height="100%"><LineChart data={data} margin={{top:5,right:12,bottom:4,left:8}}><CartesianGrid stroke="var(--adaptive-border, #123761)" vertical={false}/><XAxis dataKey="at" type="number" domain={["dataMin","dataMax"]} tickFormatter={tick} tick={{fill:"var(--adaptive-muted, #8490a6)",fontSize:10}} minTickGap={40} tickLine={false}/><YAxis domain={[0,(max:number)=>Math.max(station?.thresholds.evacuate??100,max)*1.2]} tick={{fill:"var(--adaptive-muted, #8490a6)",fontSize:10}} tickLine={false} width={40}/><Tooltip labelFormatter={v=>tick(Number(v))} formatter={v=>[`${v??"—"} cm`,"Observed depth"]} contentStyle={{background:"var(--design-panel)",border:"1px solid var(--design-line)",fontSize:12}}/><Line type="linear" dataKey="level" name="Water depth (cm)" connectNulls={false} stroke="var(--adaptive-danger, #fa7b83)" strokeWidth={1.3} dot={{r:2}} isAnimationActive={false}/></LineChart></ResponsiveContainer>:<p className="design-empty">{error?"Monitoring unavailable. Retained readings keep their original age.":"No timestamped measurements available. Missing history remains a gap."}</p>}</div>
          {station&&<details className="chart-source-details"><summary>Source, quality and timestamps</summary><p>{measurementNote(station.depth)} · {station.measurementAge}</p><p>Observation: {station.observationTier??"UNKNOWN"} · episode: {station.activeHazardTier??"None recorded"} · heartbeat: {station.connectionStatus} · latest sample: {station.depth.latestSampleQuality}</p><p>Measured timeline in PHT; invalid readings and gaps break the line.</p></details>}
        </section>
        {station?<ForecastTrendPanel key={station.id} stationId={station.id} stationControl={<label className="forecast-station">Monitoring station<select className="design-input" aria-label="Forecast station" value={station.id} onChange={e=>selectStation(e.target.value)}>{stations.map(s=><option key={s.id} value={s.id}>{s.name} · {s.id}</option>)}</select></label>}/>:<section className="forecast-panel forecast-trend design-panel"><h2>Water-depth forecast</h2><div className="forecast-trend-empty">No monitoring station selected.</div></section>}
      </div>
    </div><div className="dashboard-right">
      <section className="alert-queue design-panel" aria-labelledby="active-alerts-title"><h2 id="active-alerts-title"><i/>ACTIVE ALERTS</h2><div className="alert-queue-list">{(queue.error||legacy.error||!readIsCurrent(queue.data?.checked_at,now)||!readIsCurrent(legacy.data?.checked_at,now))&&<p role="status" className="subtle-note">Last-known episodes · current updates unconfirmed.</p>}{activeAlerts.map(a=><article className="queue-item" key={a.id}><header><strong style={{color:tierTextColor[a.severity]}}>● {a.severity}</strong><small>{a.source==="recorded_physical"?"Sensor episode":"Unverified / legacy"}</small></header><p>{a.station_name}</p><b>{a.latest_depth_cm.toFixed(1)} cm</b><p className="queue-trend">{a.ownership.owner_name??"Unassigned"} · {new Date(a.triggered_at).toLocaleString("en-PH",{timeZone:"Asia/Manila"})}</p><button className="design-button" style={{background:tierColor[a.severity]+"40",borderColor:tierColor[a.severity],color:tierTextColor[a.severity]}} onClick={()=>onViewStation(a.station_id)}>VIEW</button></article>)}{!activeAlerts.length&&<p className="design-empty">{queue.loading||legacy.loading?"Checking alert episodes…":queue.error||legacy.error?"Current episodes cannot be confirmed.":"No active sensor episodes."}</p>}</div></section>
      {station&&<><CommunityAlertThresholds station={station}/><RainfallActivityPanel key={station.id} stationId={station.id} configuration={station.configuration} physicalValidation={station.channelHealth?.calibration.physical_validation}/></>}
    </div></div>
    <details className="dashboard-review-tools" open={review} onToggle={e=>setReview(e.currentTarget.open)}><summary>Incident ownership, health and audit tools</summary>{review&&<IncidentWorkspace onViewStation={onViewStation}/>}</details>
  </div>;
}
