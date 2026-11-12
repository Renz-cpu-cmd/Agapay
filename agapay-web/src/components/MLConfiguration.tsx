"use client";
import {useMonitoring} from "@/context/MonitoringContext";
import HybridForecastPanel from "./HybridForecastPanel";
import ForecastTrendPanel from "./ForecastTrendPanel";
import MLWorkspaceHeader from "./MLWorkspaceHeader";
import {useHybridProjection} from "@/context/HybridProjectionContext";

function StationWorkspace({station}:{station:import("@/data/mockData").Station}){
  const {config,active,available}=useHybridProjection(station.id);
  return <>
    <section className="ml-station-bar design-panel"><div><span className="ml-eyebrow">SELECTED MONITORING STATION</span><h3>{station.name} <small>{station.id}</small></h3></div><span className={`ml-status ${available?"ready":""}`}><i/>{available?"Projection running":active?"Waiting for inputs":"Projection stopped"}</span></section>
    <div className="ml-overview-grid">
      <ForecastTrendPanel stationId={station.id} showDetails={false} experiment/>
      <aside className="ml-overview-aside">
        <section className="ml-card design-panel"><span className="ml-eyebrow">CURRENT SETUP</span><h3>Projection inputs</h3><dl className="ml-key-values"><div><dt>Rainfall mode</dt><dd>{config.mode==="live"?"Live rain gauge":"Historical context"}</dd></div><div><dt>Starting depth</dt><dd>{config.depthSource==="sensor"?"ESP32 measurement":`${config.initial} cm · manual`}</dd></div><div><dt>Gauge calibration</dt><dd>{station.channelHealth?.calibration.rain_configured_mm_per_tip??"—"} mm / tip · configured, physical validation pending</dd></div><div><dt>Forecast horizons</dt><dd>30 / 60 / 90 minutes</dd></div></dl><p className="ml-muted">Settings and an explicit Stop are saved on this device.</p></section>
        <section className="ml-callout"><span className="ml-eyebrow">CALIBRATION STATUS</span><h3>Calibration comes first</h3><p>Projections use the selected inputs and assumed basin dimensions. Site calibration is pending. Projected depths do not determine alerts.</p></section>
      </aside>
    </div>
  </>;
}

export default function MLConfiguration(){
  const {stations,selectedStationId,selectStation}=useMonitoring();
  const station=stations.find(s=>s.id===selectedStationId)??stations[0];
  return <div className="ml-workspace"><MLWorkspaceHeader page="configuration"/>
    {station?<><StationWorkspace station={station}/>
      <details className="ml-advanced design-panel"><summary><div><span className="ml-eyebrow">OPTIONAL CONTROLS</span><h3>Advanced projection settings</h3><p>Choose a source, adjust basin parameters, or restart the projection.</p></div><span className="ml-disclosure" aria-hidden="true">+</span></summary><HybridForecastPanel stationId={station.id} stationControl={<label className="hybrid-field">Monitoring station<select className="design-input" aria-label="ML configuration station" value={station.id} onChange={e=>selectStation(e.target.value)}>{stations.map(s=><option key={s.id} value={s.id}>{s.name} · {s.id}</option>)}</select></label>}/></details></>:<section className="ml-card design-panel"><h3>No monitoring stations</h3><p>Register a station to configure its forecast.</p></section>}
  </div>;
}
