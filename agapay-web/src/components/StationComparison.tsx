import type { Station } from "@/data/mockData";
import { measurementText, measurementNote } from "@/lib/measurements";
import { tierTextColor } from "@/data/mockData";

export default function StationComparison({stations}:{stations:readonly Station[]}) {
  const current=stations.filter(s=>s.depth.state==="current"&&s.depth.value!==null);
  return <section className="design-panel report-card station-comparison" aria-label="Current station comparison">
    <h2>CURRENT WATER DEPTH · STATION COMPARISON</h2>
    <p className="subtle-note">{current.length}/{stations.length} current valid readings. Last-known values are dated separately and excluded from current bars.</p>
    {stations.length===0&&<p className="design-empty">No monitoring stations available.</p>}
    {stations.map(station=>{
      const available=station.depth.state==="current"&&station.depth.value!==null;
      const color=available?tierTextColor[station.observationTier??"UNKNOWN"]:"var(--adaptive-muted)";
      const maximum=station.thresholds.evacuate*1.2;
      const percent=available?Math.max(0,Math.min(100,station.depth.value!/maximum*100)):0;
      return <article key={station.id}>
        <header><div><strong>{station.id}</strong><small>{station.name}</small></div><span style={{color}}>{measurementText(station.depth,1,"cm")}</span></header>
        <div className="water-bar" {...(available?{role:"progressbar","aria-label":`${station.name} depth against configured scale`,"aria-valuemin":0,"aria-valuemax":maximum,"aria-valuenow":station.depth.value!}:{"aria-hidden":true as const})}><div style={{width:`${percent}%`,background:color}}/></div>
        <p className="subtle-note">{measurementNote(station.depth)}</p>
      </article>;
    })}
  </section>;
}
