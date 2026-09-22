"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useDemo } from "@/context/DemoContext";
import { useMonitoring } from "@/context/MonitoringContext";
import { tierColor,type Alert,type AlertTier,type Station } from "@/data/mockData";
import { Modal,FigmaIcon } from "./DesignUI";
function Badge({tier}:{tier:AlertTier}) {return <span className="design-badge" style={{color:tierColor[tier],background:tierColor[tier]+"25"}}>{tier}</span>;}
function ManualAlert({stations,onClose,onCreate}:{stations:Station[];onClose:()=>void;onCreate:(stationId:string,tier:AlertTier,message:string,reason:string)=>void}) {
  const [confirm,setConfirm]=useState(false),[station,setStation]=useState("STATION_001"),[tier,setTier]=useState<AlertTier>("WARNING");
  const [message,setMessage]=useState("Heavy rainfall and rising water detected."),[reason,setReason]=useState("Officer manual intervention");
  return <Modal title={confirm?"Confirm manual alert":"Manual Alert Override"} onClose={onClose} className={confirm?"manual-confirm":"manual-form"}>
    <h2>{confirm?`Issue ${tier} Alert?`:"Manual Alert Override"}</h2>
    {confirm?<><p className="dialog-copy">This creates a demo alert in this session. Resident notification delivery is not connected.</p><dl className="dialog-summary"><div><dt>Station: </dt><dd>{station}</dd></div><div><dt>Level: </dt><dd>{tier}</dd></div><div><dt>Message: </dt><dd>{message}</dd></div><div><dt>Reason: </dt><dd>{reason}</dd></div></dl><div className="dialog-actions"><button className="design-button" onClick={()=>setConfirm(false)}>CANCEL</button><button className="design-button orange" onClick={()=>{onCreate(station,tier,message.trim(),reason.trim());onClose();}}>CONFIRM ALERT</button></div></>:
    <form onSubmit={e=>{e.preventDefault();if(message.trim()&&reason.trim())setConfirm(true);}} className="flex flex-col gap-6">
      <label>Station / Area<select aria-label="Station / Area" className="design-input" value={station} onChange={e=>setStation(e.target.value)}>{stations.map(s=><option key={s.id}>{s.id}</option>)}</select></label>
      <label>Alert Level<select aria-label="Alert Level" className="design-input" value={tier} onChange={e=>setTier(e.target.value as AlertTier)}>{["ADVISORY","WARNING","EVACUATE"].map(t=><option key={t}>{t}</option>)}</select></label>
      <label>Message<textarea aria-label="Message" className="design-input" required maxLength={500} value={message} onChange={e=>setMessage(e.target.value)}/></label>
      <label>Reason<input className="design-input" required maxLength={200} value={reason} onChange={e=>setReason(e.target.value)}/></label>
      <div className="dialog-actions"><button type="button" className="design-button" onClick={onClose}>CANCEL</button><button className="design-button orange" disabled={!message.trim()||!reason.trim()}>ISSUE ALERT</button></div>
    </form>}
  </Modal>;
}
export default function AlertsPage() {
  const {alerts,setAlerts}=useDemo(),router=useRouter();
  const {stations,sensorAlerts,dataMode}=useMonitoring();
  const [tab,setTab]=useState<"Active"|"Historical">("Active"),[search,setSearch]=useState(""),[tier,setTier]=useState("All"),[station,setStation]=useState("All");
  const [manual,setManual]=useState(false),[resolve,setResolve]=useState<Alert|null>(null);
  const displayAlerts=dataMode==="demo"?alerts:[...sensorAlerts,...alerts.filter(a=>!/^ALT-00[1-4]$/.test(a.id))];
  const rows=displayAlerts.filter(a=>(tab==="Active"?a.status==="ACTIVE":a.status==="RESOLVED")&&(tier==="All"||a.tier===tier)&&(station==="All"||a.stationId===station)&&(`${a.stationName} ${a.stationId}`).toLowerCase().includes(search.toLowerCase()));
  const clock=()=>new Date().toLocaleTimeString("en-PH",{hour:"2-digit",minute:"2-digit",timeZone:"Asia/Manila"});
  return <div className="design-page alerts-screen"><div className="design-toolbar"><div className="design-controls" role="group" aria-label="Alert history">{(["Active","Historical"] as const).map(t=><button key={t} className={`design-button ${tab===t?"active":""}`} aria-pressed={tab===t} onClick={()=>setTab(t)}>{t}</button>)}</div><button className="design-button orange" onClick={()=>setManual(true)}><FigmaIcon name="warning" size={17}/>Manual Alert</button></div>
    <div className="design-controls"><input className="design-input flex-1" aria-label="Search stations" placeholder="Search stations..." value={search} onChange={e=>setSearch(e.target.value)}/><select aria-label="Alert tier" className="design-input" value={tier} onChange={e=>setTier(e.target.value)}>{["All","EVACUATE","WARNING","ADVISORY","NORMAL"].map(t=><option key={t}>{t}</option>)}</select><select aria-label="Station filter" className="design-input" value={station} onChange={e=>setStation(e.target.value)}><option>All</option>{stations.map(s=><option key={s.id}>{s.id}</option>)}</select></div>
    <div className="design-table-wrap"><table className="design-table"><thead><tr>{["Tier","Station","Water Level","Time","Status","Action"].map(h=><th key={h}>{h}</th>)}</tr></thead><tbody>{rows.map(a=><tr key={a.id}><td><Badge tier={a.tier}/></td><td>{a.stationId}<small>{a.stationName}</small></td><td className="data-strong" style={{color:tierColor[a.tier]}}>{a.waterLevel} cm</td><td>{a.triggeredAt}{a.resolvedAt&&" – "+a.resolvedAt}</td><td><span className="design-badge" style={{color:"#00ff24",background:"#003207",padding:"3px 10px"}}>{a.status}</span></td><td><div className="actions"><button className="design-button small" onClick={()=>router.push(`/stations/${a.stationId}`)}>View</button>{a.status==="ACTIVE"&&(a.id.startsWith("SENSOR-")?<span className="subtle-note">AUTO</span>:<button className="design-button green small" onClick={()=>setResolve(a)}>Resolve</button>)}</div></td></tr>)}{!rows.length&&<tr><td colSpan={6} className="design-empty">No alerts found.</td></tr>}</tbody></table></div>
    {manual&&<ManualAlert stations={stations} onClose={()=>setManual(false)} onCreate={(stationId,tier,message,reason)=>{const s=stations.find(s=>s.id===stationId)!;setAlerts(items=>[{id:"ALT-"+crypto.randomUUID(),stationId,stationName:s.name,tier,message,reason,waterLevel:s.waterLevel,triggeredAt:clock(),status:"ACTIVE",triggeredAgo:"Just now"},...items]);setTab("Active");}}/>}
    {resolve&&<Modal title="Resolve alert" onClose={()=>setResolve(null)}><h2>Resolve {resolve.tier} Alert?</h2><p className="dialog-copy">{resolve.stationName} · {resolve.waterLevel} cm</p><p className="dialog-copy">Move this demo alert to Historical. This does not change the station’s measured level or alert threshold.</p><div className="dialog-actions"><button className="design-button" onClick={()=>setResolve(null)}>CANCEL</button><button className="design-button green" onClick={()=>{setAlerts(items=>items.map(a=>a.id===resolve.id?{...a,status:"RESOLVED",resolvedAt:clock()}:a));setResolve(null);}}>RESOLVE ALERT</button></div></Modal>}
  </div>;
}
