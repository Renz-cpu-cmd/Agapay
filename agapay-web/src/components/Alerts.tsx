"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useDemo } from "@/context/DemoContext";
import { useMonitoring } from "@/context/MonitoringContext";
import { tierColor,type Alert,type AlertTier,type Station } from "@/data/mockData";
import { Modal,FigmaIcon } from "./DesignUI";
import { useAlertResource } from "@/hooks/useAlertResource";
import { ALERT_PAGE_SIZE, alertListPath, alertTime, incidentSeverity, type AlertPage, type AlertTransition, type SensorAlert } from "@/lib/alerts";
function Badge({tier}:{tier:AlertTier}) {return <span className="design-badge" style={{color:tierColor[tier],background:tierColor[tier]+"25"}}>{tier}</span>;}
function ManualAlert({stations,onClose,onCreate}:{stations:Station[];onClose:()=>void;onCreate:(stationId:string,tier:AlertTier,message:string,reason:string)=>void}) {
  const [confirm,setConfirm]=useState(false),[station,setStation]=useState(stations[0]?.id ?? ""),[tier,setTier]=useState<AlertTier>("WARNING");
  const [message,setMessage]=useState("Heavy rainfall and rising water detected."),[reason,setReason]=useState("Officer manual intervention");
  return <Modal title={confirm?"Confirm manual alert":"Manual Alert Override"} onClose={onClose} className={confirm?"manual-confirm":"manual-form"}>
    <h2>{confirm?`Issue ${tier} Demo Alert?`:"Manual Alert Override · Demo"}</h2>
    <p className="dialog-copy">Local/session-only demo. Not delivered to residents or saved in persistent sensor history.</p>
    {confirm?<><p className="dialog-copy">This creates a demo alert in this session. Resident notification delivery is not connected.</p><dl className="dialog-summary"><div><dt>Station: </dt><dd>{station}</dd></div><div><dt>Level: </dt><dd>{tier}</dd></div><div><dt>Message: </dt><dd>{message}</dd></div><div><dt>Reason: </dt><dd>{reason}</dd></div></dl><div className="dialog-actions"><button className="design-button" onClick={()=>setConfirm(false)}>CANCEL</button><button className="design-button orange" onClick={()=>{onCreate(station,tier,message.trim(),reason.trim());onClose();}}>CONFIRM ALERT</button></div></>:
    <form onSubmit={e=>{e.preventDefault();if(message.trim()&&reason.trim())setConfirm(true);}} className="flex flex-col gap-6">
      <label>Station / Area<select aria-label="Station / Area" className="design-input" value={station} onChange={e=>setStation(e.target.value)}>{stations.map(s=><option key={s.id}>{s.id}</option>)}</select></label>
      <label>Alert Level<select aria-label="Alert Level" className="design-input" value={tier} onChange={e=>setTier(e.target.value as AlertTier)}>{["ADVISORY","WARNING","EVACUATE"].map(t=><option key={t}>{t}</option>)}</select></label>
      <label>Message<textarea aria-label="Message" className="design-input" required maxLength={500} value={message} onChange={e=>setMessage(e.target.value)}/></label>
      <label>Reason<input className="design-input" required maxLength={200} value={reason} onChange={e=>setReason(e.target.value)}/></label>
      <div className="dialog-actions"><button type="button" className="design-button" onClick={onClose}>CANCEL</button><button className="design-button orange" disabled={!station||!message.trim()||!reason.trim()}>ISSUE DEMO ALERT</button></div>
    </form>}
  </Modal>;
}
function Pagination({offset,total,busy,onChange}:{offset:number;total:number;busy:boolean;onChange:(offset:number)=>void}) {
  return <div className="design-toolbar" aria-label="Pagination">
    <span className="subtle-note">{total ? `${Math.min(offset + 1,total)}–${Math.min(offset + ALERT_PAGE_SIZE,total)} of ${total}` : "0 records"}</span>
    <div className="design-controls"><button className="design-button small" disabled={offset===0||busy} onClick={()=>onChange(Math.max(0,offset-ALERT_PAGE_SIZE))}>Previous</button><button className="design-button small" disabled={busy||offset+ALERT_PAGE_SIZE>=total} onClick={()=>onChange(offset+ALERT_PAGE_SIZE)}>Next</button></div>
  </div>;
}

function SensorHistory({episode,onClose}:{episode:SensorAlert;onClose:()=>void}) {
  const [offset,setOffset]=useState(0);
  const detail=useAlertResource<SensorAlert>(`alerts/${episode.id}`);
  const history=useAlertResource<AlertPage<AlertTransition>>(`alerts/${episode.id}/transitions?limit=${ALERT_PAGE_SIZE}&offset=${offset}`);
  const current=detail.data;
  return <Modal title="Sensor alert history" onClose={onClose}>
    <h2>Sensor alert history · {episode.station_id}</h2>
    <p className="dialog-copy">Persistent sensor episode. Device/simulator origin is not recorded for this episode; persistence does not establish physical validation.</p>
    {detail.loading&&<p role="status">Loading episode…</p>}
    {detail.error&&<p role="alert">Alert detail service unavailable. Retrying automatically.</p>}
    {current&&<dl className="dialog-summary">
      <div><dt>Status: </dt><dd>{current.status} · <Badge tier={incidentSeverity(current)}/>{current.status==="RESOLVED"?" (peak tier)":" (current tier)"}</dd></div>
      <div><dt>Triggered: </dt><dd>{alertTime(current.triggered_at)} · {current.trigger_depth_cm} cm</dd></div>
      <div><dt>Last transition: </dt><dd>{alertTime(current.last_transition_at)}</dd></div>
      <div><dt>{current.status==="RESOLVED"?"Recovery depth: ":"Latest depth: "}</dt><dd>{current.latest_depth_cm} cm</dd></div>
      {current.resolved_at&&<div><dt>Resolved: </dt><dd>{alertTime(current.resolved_at)}</dd></div>}
    </dl>}
    <h3>Severity transitions</h3>
    {history.loading&&<p role="status">Loading transitions…</p>}
    {history.error&&<p role="alert">Transition history unavailable. Retrying automatically.</p>}
    {history.data&&<>
      <ol aria-label="Severity transitions" className="flex flex-col gap-4" style={{maxHeight:"35vh",overflowY:"auto",padding:"12px 0"}}>
        {history.data.items.map(t=><li key={t.id}><strong>{t.previous_severity} → {t.new_severity}</strong><p className="subtle-note">{alertTime(t.transitioned_at)} · {t.water_depth_cm} cm · Sequence {t.sequence_no}</p></li>)}
      </ol>
      {!history.data.items.length&&<p>No transitions on this page.</p>}
      <Pagination offset={offset} total={history.data.total} busy={history.loading} onChange={setOffset}/>
    </>}
    <p className="dialog-copy">Sensor episodes resolve automatically when valid telemetry returns to NORMAL.</p>
    <button className="design-button" onClick={onClose}>CLOSE</button>
  </Modal>;
}

export default function AlertsPage() {
  const {alerts,setAlerts}=useDemo(),router=useRouter();
  const {stations,snapshot}=useMonitoring();
  const [tab,setTab]=useState<"Active"|"Historical">("Active"),[search,setSearch]=useState(""),[tier,setTier]=useState("All"),[station,setStation]=useState("All");
  const [offset,setOffset]=useState(0);
  const [manual,setManual]=useState(false),[resolve,setResolve]=useState<Alert|null>(null),[selected,setSelected]=useState<SensorAlert|null>(null);
  const resource=useAlertResource<AlertPage<SensorAlert>>(alertListPath(tab==="Active"?"ACTIVE":"RESOLVED",station,tier,offset));
  // Only API metadata supplies operational names. Monitoring's bundled demo
  // stations are still usable in the separate manual prototype, never here.
  const names=new Map(snapshot?.stations.map(s=>[s.station_id,s.station_name])??[]);
  const stationIds=Array.from(new Set([...names.keys(),...(resource.data?.items.map(a=>a.station_id)??[]),...(station!=="All"?[station]:[])])).sort();
  const matchesSearch=(id:string,name:string)=>`${id} ${name}`.toLowerCase().includes(search.trim().toLowerCase());
  const rows=resource.data?.items.filter(a=>(tier==="All"||incidentSeverity(a)===tier)&&matchesSearch(a.station_id,names.get(a.station_id)??""))??[];
  // Seeded mock incidents stay out of both persistent history and manual entries.
  const demos=alerts.filter(a=>!/^ALT-00[1-4]$/.test(a.id)&&(tab==="Active"?a.status==="ACTIVE":a.status==="RESOLVED")&&(tier==="All"||a.tier===tier)&&(station==="All"||a.stationId===station)&&matchesSearch(a.stationId,a.stationName));
  const clock=()=>alertTime(new Date().toISOString());
  return <div className="design-page alerts-screen">
    <div className="design-toolbar"><div className="design-controls" role="group" aria-label="Alert history">{(["Active","Historical"] as const).map(t=><button key={t} className={`design-button ${tab===t?"active":""}`} aria-pressed={tab===t} onClick={()=>{setTab(t);setOffset(0);}}>{t}</button>)}</div><button className="design-button orange" onClick={()=>setManual(true)}><FigmaIcon name="warning" size={17}/>Manual Alert · Demo</button></div>
    <div className="design-controls"><input className="design-input flex-1" aria-label="Search stations" placeholder="Search this page..." value={search} onChange={e=>setSearch(e.target.value)}/><select aria-label={tab==="Historical"?"Peak alert tier":"Alert tier"} className="design-input" value={tier} onChange={e=>{setTier(e.target.value);setOffset(0);}}>{["All","EVACUATE","WARNING","ADVISORY"].map(t=><option key={t}>{t}</option>)}</select><select aria-label="Station filter" className="design-input" value={station} onChange={e=>{setStation(e.target.value);setOffset(0);}}><option>All</option>{stationIds.map(id=><option key={id} value={id}>{names.get(id)?`${id} · ${names.get(id)}`:id}</option>)}</select></div>
    <section aria-label="Persistent sensor alerts">
      <h2>Persistent sensor alerts</h2>
      <p className="subtle-note">Backend episodes · automatically resolved by valid telemetry · times in Asia/Manila (PHT). Device/simulator origin is not recorded per episode.</p>
      <p className="subtle-note">Search{tab==="Historical"?" and peak-tier filtering apply":" applies"} to this page of up to 50 episodes. Use Next to inspect older pages. Counts are before these page filters.</p>
      <div className="design-table-wrap"><table className="design-table"><thead><tr>{[tab==="Historical"?"Peak Tier":"Current Tier","Station",tab==="Historical"?"Trigger Depth":"Latest Depth","Time (PHT)","Status","Action"].map(h=><th key={h}>{h}</th>)}</tr></thead><tbody>
        {resource.loading&&<tr><td colSpan={6} className="design-empty" role="status">Loading alerts…</td></tr>}
        {resource.error&&<tr><td colSpan={6} className="design-empty" role="alert">Alert service unavailable. Sensor alert state cannot be confirmed. Retrying automatically.</td></tr>}
        {rows.map(a=><tr key={a.id}><td><Badge tier={incidentSeverity(a)}/></td><td>{a.station_id}{names.get(a.station_id)&&<small>{names.get(a.station_id)}</small>}</td><td className="data-strong" style={{color:tierColor[incidentSeverity(a)]}}>{a.status==="RESOLVED"?a.trigger_depth_cm:a.latest_depth_cm} cm</td><td><small>Triggered {alertTime(a.triggered_at)}</small><small>{a.status==="RESOLVED"?`Resolved ${alertTime(a.resolved_at)}`:`Changed ${alertTime(a.last_transition_at)}`}</small></td><td><span className="design-badge">{a.status}</span></td><td><div className="actions"><button className="design-button small" onClick={()=>setSelected(a)}>History</button><button className="design-button small" onClick={()=>router.push(`/stations/${encodeURIComponent(a.station_id)}`)}>View</button>{a.status==="ACTIVE"&&<span className="subtle-note">AUTO</span>}</div></td></tr>)}
        {resource.data&&!rows.length&&<tr><td colSpan={6} className="design-empty">{resource.data.total===0?`No ${tab==="Active"?"active":"historical"} sensor alerts${station!=="All"||tier!=="All"?" matching the filters":""}.`:"No matching sensor alerts on this page. Change filters or use another page."}</td></tr>}
      </tbody></table></div>
      {resource.data&&<Pagination offset={offset} total={resource.data.total} busy={resource.loading} onChange={setOffset}/>}
      {tab==="Historical"&&<p className="subtle-note">Trigger depth is the episode’s first alert reading, not peak depth. Peak tier is the highest severity reached.</p>}
    </section>
    <section aria-label="Manual demo alerts" className="design-panel" style={{padding:16}}>
      <h2>Manual demo alerts · {tab}</h2><p className="dialog-copy">Local/session-only. Not delivered to residents. Not part of persistent sensor history. Resets on reload.</p>
      {demos.map(a=><div key={a.id} className="design-toolbar"><div><Badge tier={a.tier}/> <strong>{a.stationId}</strong> · {a.stationName}<p className="subtle-note">DEMO · {a.status} · {a.triggeredAt}{a.resolvedAt&&` – ${a.resolvedAt}`}</p><p>{a.message}</p></div>{a.status==="ACTIVE"&&<button className="design-button green small" onClick={()=>setResolve(a)}>Resolve demo</button>}</div>)}
      {!demos.length&&<p className="subtle-note">No matching manual demo alerts.</p>}
    </section>
    {selected&&<SensorHistory key={selected.id} episode={selected} onClose={()=>setSelected(null)}/>}
    {manual&&<ManualAlert stations={stations} onClose={()=>setManual(false)} onCreate={(stationId,tier,message,reason)=>{const s=stations.find(s=>s.id===stationId);setAlerts(items=>[{id:"ALT-"+crypto.randomUUID(),stationId,stationName:s?.name??stationId,tier,message,reason,waterLevel:s?.waterLevel??0,triggeredAt:clock(),status:"ACTIVE",triggeredAgo:"Just now"},...items]);setTab("Active");setOffset(0);}}/>}
    {resolve&&<Modal title="Resolve demo alert" onClose={()=>setResolve(null)}><h2>Resolve {resolve.tier} Demo Alert?</h2><p className="dialog-copy">{resolve.stationName}</p><p className="dialog-copy">Move this local demo to Historical. Persistent sensor episodes and station readings are unchanged. Nothing is delivered to residents.</p><div className="dialog-actions"><button className="design-button" onClick={()=>setResolve(null)}>CANCEL</button><button className="design-button green" onClick={()=>{setAlerts(items=>items.map(a=>a.id===resolve.id?{...a,status:"RESOLVED",resolvedAt:clock()}:a));setResolve(null);}}>RESOLVE DEMO</button></div></Modal>}
  </div>;
}
