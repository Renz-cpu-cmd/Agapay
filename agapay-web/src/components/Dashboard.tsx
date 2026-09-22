"use client";
import { LineChart,Line,XAxis,YAxis,CartesianGrid,Tooltip,ResponsiveContainer } from "recharts";
import { useDemo } from "@/context/DemoContext";
import { useSos } from "@/context/SosContext";
import { useMonitoring } from "@/context/MonitoringContext";
import { tierColor,trendLabel } from "@/data/mockData";
import StationMap from "./StationMap";
import CommunityAlertThresholds from "./CommunityAlertThresholds";
export default function Dashboard({onViewStation}:{onViewStation:(id:string)=>void}) {
  const {alerts}=useDemo(),{page:sosPage,error:sosError}=useSos();
  const {stations,sensorAlerts,dataMode}=useMonitoring();
  const activeAlerts=(dataMode==="demo"?alerts:sensorAlerts).filter(a=>a.status==="ACTIVE").sort((a,b)=>["EVACUATE","WARNING","ADVISORY","NORMAL","UNKNOWN"].indexOf(a.tier)-["EVACUATE","WARNING","ADVISORY","NORMAL","UNKNOWN"].indexOf(b.tier));
  const station=stations[0],online=stations.filter(s=>s.isOnline).length,highest=[...stations].sort((a,b)=>b.waterLevel-a.waterLevel)[0];
  const stats=[
    {title:"Monitoring stations",value:stations.length,sub:`${online} online / ${stations.length-online} offline`,color:"#7db3ff"},
    {title:"Active alerts",value:activeAlerts.length,sub:`${activeAlerts.filter(a=>a.tier==="EVACUATE").length} Critical Evacuation Alert`,color:"#ff7500"},
    {title:"Active SOS",value:sosPage?sosPage.counts.ACTIVE:"—",sub:sosError?"Status unavailable":!sosPage?"Connecting…":"Practice · "+(sosPage.counts.ACTIVE?"Needs Response":"No active requests"),color:"#ff0000"},
    {title:"Highest level",value:highest.waterLevel+" cm",sub:highest.id,color:tierColor[highest.status]}
  ];
  return <div className="dashboard-screen"><div className="dashboard-stats">{stats.map(s=><section className="dashboard-stat" key={s.title}><h2>{s.title}</h2><strong style={{color:s.color}}>{s.value}</strong><p>{s.sub}</p></section>)}</div>
    <div className="dashboard-body"><div className="dashboard-left"><StationMap onViewStation={onViewStation}/>
      <section className="dashboard-chart design-panel" aria-label="Water depth chart"><div className="chart-heading"><h2>Water Depth - {station.id}</h2><span style={{color:tierColor[station.status]}}>{station.status === "UNKNOWN" ? "Waiting for data" : `${station.waterLevel} cm　${trendLabel[station.trend]}`}</span></div>
        <div style={{height:200}}><ResponsiveContainer width="100%" height="100%"><LineChart data={station.waterHistory.slice(-16)} margin={{top:5,right:12,bottom:4,left:8}}><CartesianGrid stroke="#123761" vertical={false}/><XAxis dataKey="time" tick={{fill:"#8490a6",fontSize:10}} tickLine={false} axisLine={{stroke:"#002967"}} interval={3}/><YAxis domain={[0,120]} ticks={[0,30,60,80,120]} tick={{fill:"#8490a6",fontSize:10}} tickLine={false} axisLine={{stroke:"#002967"}} width={40}/><Tooltip contentStyle={{background:"#00112e",border:"1px solid #6496db",fontSize:12}}/><Line type="monotone" dataKey="level" name="Water depth (cm)" stroke="#fa7b83" strokeWidth={1.3} dot={{r:2}} isAnimationActive={false}/></LineChart></ResponsiveContainer></div>
      </section></div>
      <div className="dashboard-right"><section className="alert-queue design-panel" aria-labelledby="active-alerts-title"><h2 id="active-alerts-title"><i/>ACTIVE ALERTS</h2><div className="alert-queue-list">{activeAlerts.map(a=><article className="queue-item" key={a.id}><header><strong style={{color:tierColor[a.tier]}}>● {a.tier}</strong><small>{a.triggeredAgo}</small></header><p>{a.stationName}</p><b>{a.waterLevel} cm</b><p className="queue-trend">{trendLabel[stations.find(s=>s.id===a.stationId)?.trend??"stable"]}</p><button className="design-button" style={{background:tierColor[a.tier]+"40",borderColor:tierColor[a.tier],color:tierColor[a.tier]}} onClick={()=>onViewStation(a.stationId)}>VIEW</button></article>)}{!activeAlerts.length&&<p className="design-empty">No active alerts.</p>}</div></section><CommunityAlertThresholds station={station}/></div>
    </div>
  </div>;
}
