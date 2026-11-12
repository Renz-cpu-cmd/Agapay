"use client";
import {useEffect,useState} from "react";
import {accountRequest} from "@/lib/accounts";
import {useAccount} from "@/context/AccountContext";
type Operations={state:string;revision:number;identity_version:number;station_name:string;barangay:string|null;municipality:string|null;ingestion:string;hazard_policy:string;external_sensor_notifications:boolean;local_alarm_policy:string};
export default function StationAdministration({stationId,onSaved}:{stationId:string;onSaved:()=>void}){
  const {user}=useAccount();
  const [current,setCurrent]=useState<Operations|null>(null),[error,setError]=useState(""),[busy,setBusy]=useState(false),[blocked,setBlocked]=useState(false);
  const [reason,setReason]=useState(""),[nextState,setNextState]=useState("maintenance");
  async function read(){if(busy)return;setBusy(true);setError("");setBlocked(true);try{const next=await accountRequest<Operations>(`stations/${stationId}/operations`);setCurrent(next);setBlocked(false);}catch(e){setError(e instanceof Error?e.message:"Lifecycle unavailable");}finally{setBusy(false);}}
  useEffect(()=>{let active=true;setCurrent(null);setError("");setBlocked(false);void accountRequest<Operations>(`stations/${stationId}/operations`).then(value=>{if(active)setCurrent(value);}).catch(()=>{if(active)setError("Station operations unavailable");});return()=>{active=false;};},[stationId]);
  async function save(method:"POST"|"PATCH",path:string,body:Record<string,unknown>){
    if(!current||busy||blocked)return;setBusy(true);setError("");
    try{const next=await accountRequest<Operations>(`stations/${stationId}/${path}`,method,{expected_revision:current.revision,reason,...body});setCurrent(next);setReason("");onSaved();}
    catch(e){setError(e instanceof Error?e.message:"Update failed");setBlocked(true);}
    finally{setBusy(false);}
  }
  const allowed=user.role==="admin"&&!busy&&!blocked&&Boolean(current)&&reason.trim().length>=3;
  return <section className="design-panel p-4 flex flex-col gap-3"><h2>Station lifecycle and metadata</h2><p className="subtle-note">Maintenance keeps observations and hazard escalation visible, holds recovery and suppresses external sensor push. Existing incidents are retained. Local device alarms continue offline.</p>
    {current&&<><p>State {current.state} · revision {current.revision} · identity version {current.identity_version}</p><p>Ingestion {current.ingestion} · {current.hazard_policy} · external sensor push {current.external_sensor_notifications?"enabled":"suppressed"}</p><p className="subtle-note">{current.local_alarm_policy}</p></>}
    {user.role==="admin"&&current&&<><label className="flex flex-col gap-1">Change reason<input className="design-input" value={reason} maxLength={500} onChange={e=>setReason(e.target.value)}/></label><form className="flex flex-col gap-3" onSubmit={e=>{e.preventDefault();const form=new FormData(e.currentTarget);void save("PATCH","metadata",{station_name:form.get("station_name"),barangay:form.get("barangay"),municipality:form.get("municipality")});}} key={`${stationId}-${current.revision}`}>
      <label className="flex flex-col gap-1">Station name<input className="design-input" name="station_name" defaultValue={current.station_name} required maxLength={255}/></label><label className="flex flex-col gap-1">Station barangay (descriptive text)<input className="design-input" name="barangay" defaultValue={current.barangay??""} maxLength={255}/></label><label className="flex flex-col gap-1">Municipality<input className="design-input" name="municipality" defaultValue={current.municipality??""} maxLength={255}/></label><button className="design-button" disabled={!allowed}>Save metadata</button></form>
      <label className="flex flex-col gap-1">Lifecycle state<select className="design-input" value={nextState} onChange={e=>setNextState(e.target.value)}>{["active","maintenance","inactive","decommissioned"].map(state=><option key={state}>{state}</option>)}</select></label><button className="design-button" disabled={!allowed||nextState===current.state} onClick={()=>void save("POST","lifecycle",{expected_identity_version:current.identity_version,state:nextState})}>Apply lifecycle change</button><p className="subtle-note">Decommissioning revokes station credentials and preserves incident history. Recommissioning and geometry changes use the reviewed commissioning/configuration API.</p></>}
    {error&&<p role="alert">{error} Refresh and manually review before another write.</p>}<button className="design-button" onClick={()=>void read()} disabled={busy}>Refresh station operations</button>
  </section>;
}
