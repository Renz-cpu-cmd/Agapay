"use client";
import {useState} from "react";
import Link from "next/link";
import {useAccount} from "@/context/AccountContext";
import {useSos} from "@/context/SosContext";
import {useMonitoring} from "@/context/MonitoringContext";
import {useAlertResource} from "@/hooks/useAlertResource";
import {useEvidenceClock} from "@/hooks/useEvidenceClock";
import {accountRequest} from "@/lib/accounts";
import {alertTime} from "@/lib/alerts";
import {elapsedLabel,readIsCurrent,reviewAction,stationFaults,type CommandEpisode,type CommandQueue} from "@/lib/staff-workspaces";
import {measurementLabel,measurementText} from "@/lib/measurements";
import {tierTextColor} from "@/data/mockData";
import StationMap from "./StationMap";
import MeasuredTrend from "./MeasuredTrend";
import ForecastPanel from "./ForecastTrendPanel";

function OwnershipAction({episode,current,onRefresh}:{episode:CommandEpisode;current:boolean;onRefresh:()=>void}) {
  const {user}=useAccount();
  const [reason,setReason]=useState(""),[busy,setBusy]=useState(false),[blocked,setBlocked]=useState(false),[message,setMessage]=useState("");
  const own=episode.ownership.owner_id===user.id,release=own||(user.role==="admin"&&episode.ownership.owner_id!==null),available=release||episode.ownership.owner_id===null;
  async function save(){
    if(!current||!available||blocked||busy||reason.trim().length<3)return;
    setBusy(true);
    try{await accountRequest(`alerts/${episode.id}/ownership`,"POST",{expected_revision:episode.ownership.revision,
      expected_telemetry_id:episode.latest_telemetry_id,action:release?"release":"take",reason:reason.trim()});
      setMessage("Responsibility recorded. Refresh and review the saved ownership.");setReason("");}
    catch(e){setMessage(e instanceof Error?e.message:"Ownership unavailable. Refresh and manually review.");}
    finally{setBusy(false);setBlocked(true);}
  }
  return <div className="ownership-action">
    {available&&!blocked&&<form onSubmit={e=>{e.preventDefault();void save();}}><label>Reason for {release?"releasing":"taking"} review responsibility
      <input className="design-input" maxLength={500} value={reason} onChange={e=>setReason(e.target.value)}/></label>
      <button className="design-button" disabled={!current||busy||reason.trim().length<3}>{busy?"Saving…":release?"Release responsibility":"Take responsibility"}</button></form>}
    {message&&<p role="status">{message}</p>}{blocked&&<button className="design-button" onClick={onRefresh}>Refresh and review</button>}
  </div>;
}

export default function IncidentWorkspace({onViewStation}:{onViewStation:(id:string)=>void}) {
  const {stations,selectedStationId,selectStation,error,loading,snapshot}=useMonitoring();
  const {page:sosPage,error:sosError,syncedAt:sosSyncedAt}=useSos();
  const [offset,setOffset]=useState(0),[scope,setScope]=useState<"operational"|"unverified">("operational"),[revision,setRevision]=useState(0);
  const queueRead=useAlertResource<CommandQueue>(`alerts/command-queue?scope=${scope}&limit=20&offset=${offset}&refresh=${revision}`);
  const scopeMismatch=Boolean(queueRead.data&&queueRead.data.scope!==scope);
  const queue={...queueRead,data:scopeMismatch?null:queueRead.data,error:queueRead.error||scopeMismatch};
  const now=useEvidenceClock();
  const current=readIsCurrent(queue.data?.checked_at,now)&&!queue.error;
  const selected=stations.find(s=>s.id===selectedStationId)??stations.find(s=>s.id===queue.data?.items[0]?.station_id)??stations[0];
  const faults=stations.filter(s=>s.administrativeStatus==="active"&&stationFaults(s).length>0);
  return <div className="design-page staff-decisions incident-workspace">
    <header className="workspace-heading"><div><p className="workspace-eyebrow">Staff command center</p><h1>What needs attention now?</h1><p>Review sensor incidents, verify evidence and record responsibility.</p></div><Link className="design-button" href="/alerts">Authority notices and incident history</Link></header>
    <section className="design-panel decision-queue" aria-labelledby="incident-queue-title">
      <div className="design-toolbar"><div><h2 id="incident-queue-title">Prioritized incident queue</h2><p className="subtle-note">Critical tier first, then warning and advisory; oldest first within each tier. Sensor tiers are observations, not authority orders.</p></div><button className="design-button" onClick={()=>setRevision(n=>n+1)}>Refresh queue</button></div>
      <div className="design-controls" role="group" aria-label="Incident evidence scope">{(["operational","unverified"] as const).map(value=><button key={value} className="design-button" aria-pressed={scope===value} onClick={()=>{setScope(value);setOffset(0);}}>{value==="operational"?"Recorded physical sources":"Legacy review"}</button>)}</div>
      <p role="status">{queue.data?`${queue.data.counts.operational} physical-source · ${queue.data.counts.unverified} unverified / legacy active episodes across all pages`:"Checking both evidence scopes…"}</p>
      <p className="subtle-note">Recorded physical identity is checked for both the trigger and latest episode observation. Ownership records review responsibility; it does not mean dispatch.</p>
      {queue.loading&&<p role="status">Checking persistent incidents…</p>}
      {queue.error&&<p role="alert">Incident service unavailable. The current queue cannot be confirmed.</p>}
      {queue.data&&<><p role="status">{current?"Queue checked":"Last-known queue; refresh before acting"} {alertTime(queue.data.checked_at)} · {queue.data.total} {scope==="operational"?"physical-source":"legacy"} active episode(s)</p>
        <ol className="decision-episodes">{queue.data.items.map(episode=>{const station=stations.find(s=>s.id===episode.station_id);return <li key={episode.id}><article className="decision-episode">
          <header><div><span className="operational-state" style={{color:tierTextColor[episode.severity]}}>{episode.severity} · sensor episode #{episode.id}</span><h3>{episode.station_name}</h3><p>{episode.station_id} · {elapsedLabel(episode.triggered_at)}</p></div><button className="design-button" onClick={()=>onViewStation(episode.station_id)}>Inspect reading</button></header>
          <dl className="evidence-grid"><div><dt>Review owner</dt><dd>{episode.ownership.owner_name??"Unassigned"}{episode.ownership.changed_at&&<p className="subtle-note">Changed {alertTime(episode.ownership.changed_at)}</p>}</dd></div><div><dt>Episode began</dt><dd>{alertTime(episode.triggered_at)}</dd></div><div><dt>Verified area bindings</dt><dd>{episode.areas.length?episode.areas.map(a=>`${a.name} (${a.id})`).join("; "):"No verified area binding recorded"}</dd></div><div><dt>Current measurement</dt><dd>{station?`${measurementText(station.depth,1,"cm")} · ${measurementLabel(station.depth)} · ${station.depth.reason} · measured ${station.measurementAge}`:"Unavailable; inspect station evidence"}</dd></div></dl>
          <p className="next-action"><strong>Next action:</strong> {reviewAction(station)}</p>
          <OwnershipAction key={`${revision}-${scope}-${episode.id}`} episode={episode} current={current} onRefresh={()=>setRevision(n=>n+1)}/>
        </article></li>;})}</ol>
        {!queue.data.items.length&&<p className="design-empty">No active episodes in this evidence scope. Missing observations and service faults still require review.</p>}
        <div className="design-controls"><button className="design-button" disabled={!offset} onClick={()=>setOffset(Math.max(0,offset-20))}>Previous incidents</button><span>Showing {queue.data.items.length?offset+1:0}–{offset+queue.data.items.length} of {queue.data.total}</span><button className="design-button" disabled={!queue.data.has_more} onClick={()=>setOffset(offset+20)}>Next incidents</button></div>
      </>}
    </section>
    <div className="staff-overview-grid">
      <section className="design-panel p-4"><h2>Station attention</h2><p className="subtle-note">Water, rain, heartbeat and broker observations are independent. Administration is shown separately.</p>
        {error&&<p role="status">Monitoring unavailable; these are last-known observations.</p>}{loading&&<p role="status">Checking station health…</p>}
        <p>{faults.length} active station(s) need health review · {stations.filter(s=>s.administrativeStatus==="maintenance").length} in maintenance</p>
        <ul className="station-attention-list">{stations.map(s=><li key={s.id}><button className="design-button" onClick={()=>onViewStation(s.id)}>{s.name}</button><p>{stationFaults(s).join(" · ")||"All four observed channels healthy"}</p></li>)}</ul>
        {!stations.length&&!loading&&<p>No station evidence available.</p>}<Link href="/system-health">Open service and delivery diagnostics</Link>
      </section>
      <section className="design-panel p-4"><h2>Area and station context</h2><p className="subtle-note">Station locations and verified area bindings are context. Flood extent, road passability and affected-area boundaries are not inferred from a station pin.</p>
        <StationMap onViewStation={onViewStation} selectedStationId={selected?.id??""} onSelectStation={selectStation}/>
      </section>
    </div>
    {selected&&<section className="design-panel p-4"><div className="design-controls"><h2>Measured trend</h2><label>Station<select className="design-input" value={selected.id} onChange={e=>selectStation(e.target.value)}>{stations.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select></label></div><MeasuredTrend station={selected} maximumGapSeconds={snapshot?.stale_after_seconds??30}/></section>}
    <section className="design-panel p-4"><h2>Published forecasts</h2><p className="subtle-note">Published products retain their approval, version and expiry. Projections are in the ML workspace and do not drive this incident queue.</p>{selected&&<ForecastPanel key={selected.id} stationId={selected.id}/>}<Link href="/ml-configuration">Open ML workspace</Link></section>
    <section className="design-panel p-4"><h2>Response workspace</h2><p>{sosError?"Request count unavailable":sosPage?`${readIsCurrent(sosSyncedAt??undefined,now)?"":"Last known count: "}${sosPage.counts.ACTIVE} active SOS request(s)`:"Checking test request count…"}. Test acknowledgement does not mean a responder was sent.</p><Link className="design-button" href="/sos">Open SOS and drill actions</Link></section>
  </div>;
}
