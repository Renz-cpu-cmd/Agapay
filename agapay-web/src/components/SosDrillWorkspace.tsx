"use client";
import {useEffect,useState} from "react";
import {accountRequest,AccountError} from "@/lib/accounts";
import {useAccount} from "@/context/AccountContext";
import {sosTime,type SosRequest} from "@/lib/sos";

type Person={id:number;name:string;role:string};
type Shift={user_id:number;starts_at:string;ends_at:string};
type Contact={label:string;channel:string;contact:string};
type Settings={coordinator_id:number|null;timezone:string;assignment_seconds:number;acceptance_seconds:number;departure_seconds:number;arrival_seconds:number;review_seconds:number;shifts:Shift[];fallback_contacts:Contact[]};
type Policy={version:number;settings:Settings;activation_requirements:string[]};
type Activity={started:boolean;request_version:number;phase?:string;attention?:string;coordinator_name?:string;responder_name?:string;due_at?:string;incident_reference?:string;closure_reason?:string;events:{id:number;message:string;created_at:string;actor_name?:string}[];fallback_contacts?:Contact[]};
const limits=["assignment_seconds","acceptance_seconds","departure_seconds","arrival_seconds","review_seconds"] as const;
const actions=["assign","contact_attempt","accept","depart","arrive","handoff","unavailable","review_escalation","correlate","close"];

function PolicyEditor({policy,people,blocked,onSaved,onFailed}:{policy:Policy;people:Person[];blocked:boolean;onSaved:()=>Promise<void>;onFailed:(e:unknown)=>void}){
  const [draft,setDraft]=useState<Settings>(structuredClone(policy.settings)),[reason,setReason]=useState(""),[busy,setBusy]=useState(false);
  async function save(){if(busy||blocked)return;setBusy(true);try{await accountRequest("sos-response/policy","PATCH",{...draft,expected_version:policy.version,reason});setReason("");await onSaved();}catch(e){onFailed(e);}finally{setBusy(false);}}
  const now=new Date().toISOString().slice(0,16)+":00Z",end=new Date(Date.now()+86400000).toISOString().slice(0,16)+":00Z";
  return <details><summary>Configure drill policy and duty hours · revision {policy.version}</summary><form className="flex flex-col gap-3 mt-3" onSubmit={e=>{e.preventDefault();void save();}}>
    <p>Drill defaults are planning targets. Enter actual participating staff and exercise contacts. All duty timestamps below are UTC.</p>
    <label>Drill coordinator<select className="design-input w-full" required value={draft.coordinator_id??""} onChange={e=>setDraft({...draft,coordinator_id:Number(e.target.value)})}><option value="">Choose staff</option>{people.map(p=><option key={p.id} value={p.id}>{p.name} · #{p.id}</option>)}</select></label>
    <label>Policy timezone (duty entries use UTC)<input className="design-input w-full" required value={draft.timezone} onChange={e=>setDraft({...draft,timezone:e.target.value})}/></label>
    {limits.map(key=><label key={key}>{key.replaceAll("_"," ")}<input className="design-input w-full" type="number" min={5} max={86400} required value={draft[key]} onChange={e=>setDraft({...draft,[key]:Number(e.target.value)})}/></label>)}
    <h4>Duty roster · order determines fallback order</h4>{draft.shifts.map((s,i)=><fieldset className="flex flex-col gap-2 border border-slate-600 p-2" key={i}>
      <select aria-label={`Duty staff ${i+1}`} className="design-input" required value={s.user_id||""} onChange={e=>setDraft({...draft,shifts:draft.shifts.map((v,n)=>n===i?{...v,user_id:Number(e.target.value)}:v)})}><option value="">Choose staff</option>{people.map(p=><option key={p.id} value={p.id}>{p.name} · #{p.id}</option>)}</select>
      {(["starts_at","ends_at"] as const).map(key=><label key={key}>{key==="starts_at"?"Starts (UTC)":"Ends (UTC)"}<input className="design-input w-full" type="datetime-local" required value={s[key].slice(0,16)} onChange={e=>setDraft({...draft,shifts:draft.shifts.map((v,n)=>n===i?{...v,[key]:e.target.value+":00Z"}:v)})}/></label>)}
      <button type="button" className="design-button" onClick={()=>setDraft({...draft,shifts:draft.shifts.filter((_,n)=>n!==i)})}>Remove shift</button></fieldset>)}
    <button type="button" className="design-button" onClick={()=>setDraft({...draft,shifts:[...draft.shifts,{user_id:0,starts_at:now,ends_at:end}]})}>Add drill duty shift</button>
    <h4>Fallback contacts · no automatic calls or messages</h4>{draft.fallback_contacts.map((c,i)=><fieldset className="flex flex-col gap-2 border border-slate-600 p-2" key={i}>
      <input aria-label={`Fallback label ${i+1}`} className="design-input" placeholder="Contact label" required minLength={3} maxLength={100} value={c.label} onChange={e=>setDraft({...draft,fallback_contacts:draft.fallback_contacts.map((v,n)=>n===i?{...v,label:e.target.value}:v)})}/>
      <select aria-label={`Fallback channel ${i+1}`} className="design-input" value={c.channel} onChange={e=>setDraft({...draft,fallback_contacts:draft.fallback_contacts.map((v,n)=>n===i?{...v,channel:e.target.value}:v)})}>{["phone","radio","in_person"].map(v=><option key={v}>{v}</option>)}</select>
      <input aria-label={`Fallback contact ${i+1}`} className="design-input" placeholder="Exercise contact or radio channel" required minLength={3} maxLength={150} value={c.contact} onChange={e=>setDraft({...draft,fallback_contacts:draft.fallback_contacts.map((v,n)=>n===i?{...v,contact:e.target.value}:v)})}/>
      <button type="button" className="design-button" onClick={()=>setDraft({...draft,fallback_contacts:draft.fallback_contacts.filter((_,n)=>n!==i)})}>Remove contact</button></fieldset>)}
    <button type="button" className="design-button" onClick={()=>setDraft({...draft,fallback_contacts:[...draft.fallback_contacts,{label:"",channel:"radio",contact:""}]})}>Add fallback contact</button>
    <label>Review reason<input className="design-input w-full" required minLength={3} maxLength={500} value={reason} onChange={e=>setReason(e.target.value)}/></label>
    <button className="design-button" disabled={busy||blocked||!draft.shifts.length||!draft.fallback_contacts.length}>Save drill policy</button>
  </form></details>;
}

export default function SosDrillWorkspace({requestId,onStarted}:{requestId:number;onStarted:(started:boolean)=>void}){
  const {user}=useAccount();
  const [data,setData]=useState<Activity|null>(null),[policy,setPolicy]=useState<Policy|null>(null),[people,setPeople]=useState<Person[]>([]);
  const [request,setRequest]=useState<SosRequest|null>(null),[error,setError]=useState(""),[blocked,setBlocked]=useState(false),[busy,setBusy]=useState(false),[revision,setRevision]=useState(0);
  const [action,setAction]=useState("assign"),[reason,setReason]=useState(""),[reference,setReference]=useState(""),[responder,setResponder]=useState(""),[incident,setIncident]=useState("");
  const [channel,setChannel]=useState("radio"),[outcome,setOutcome]=useState("no_answer"),[closure,setClosure]=useState("exercise_complete"),[incidents,setIncidents]=useState<{id:number;label:string}[]>([]),[incidentLabel,setIncidentLabel]=useState("");
  function discard(){setReason("");setReference("");setResponder("");setIncident("");setIncidentLabel("");}
  function fail(e:unknown){
    if(e instanceof AccountError&&e.status===422){setError(e.message);return;}
    setBlocked(true);discard();setError((e instanceof Error?e.message:"Action not confirmed")+" Refresh and manually review before another submission.");
  }
  async function load(){
    setBusy(true);
    try{const [activity,p,staff,r,groups]=await Promise.all([accountRequest<Activity>(`sos-response/${requestId}`),accountRequest<Policy>("sos-response/policy"),accountRequest<Person[]>("sos-response/staff"),accountRequest<SosRequest>(`sos/${requestId}`),accountRequest<{id:number;label:string}[]>("sos-response/incidents")]);setData(activity);setPolicy(p);setPeople(staff);setRequest(r);setIncidents(groups);onStarted(activity.started);setBlocked(false);setError("");discard();setRevision(v=>v+1);}catch(e){fail(e);}finally{setBusy(false);}
  }
  useEffect(()=>{void load();},[requestId]); // Explicit refresh owns the form's snapshot; no background mutation replay.
  async function submit(start=false){
    if(busy||blocked||!data||!policy)return;setBusy(true);setError("");
    try{const next=await accountRequest<Activity>(`sos-response/${requestId}/${start?"start":"actions"}`,"POST",start?{expected_version:data.request_version,policy_version:policy.version,reason}:{expected_version:data.request_version,action,reason,...(responder?{responder_id:Number(responder)}:{}),...(incident?{incident_id:Number(incident)}:{}),...(reference?{reference}:{}),...(action==="contact_attempt"?{channel,outcome}:{}),...(action==="close"?{closure_reason:closure}:{})});setData(next);onStarted(next.started);discard();if(action==="close"&&!start) setRequest(old=>old?{...old,status:"RESOLVED"}:old);}catch(e){fail(e);}finally{setBusy(false);}
  }
  return <section className="design-panel p-3 flex flex-col gap-3"><h3>Response drill workspace</h3><p className="subtle-note">Timed escalation requires the drill deadline worker; a displayed due time does not confirm it ran. Exercise only. No operational dispatch, calls or emergency messages are sent. Acknowledgement means review only.</p>
    <button className="design-button" disabled={busy} onClick={()=>void load()}>Refresh and review drill</button>{error&&<p role="alert">{error}</p>}
    {blocked&&<p>Edits discarded. Actions are locked until an explicit refresh succeeds.</p>}
    {policy&&user.role==="admin"&&!blocked&&<PolicyEditor key={revision} policy={policy} people={people} blocked={busy||blocked} onSaved={load} onFailed={fail}/>}
    {data&&<><p>Recorded stage: {data.phase??"Not started"} · {data.attention??"No response action recorded"}</p><p>Coordinator: {data.coordinator_name??"Unassigned"} · Responder: {data.responder_name??"No assignment"}</p>{data.due_at&&<p>Drill review due {sosTime(data.due_at)} PHT · an overdue target is not evidence of arrival.</p>}{data.incident_reference&&<p>Incident {data.incident_reference} · individual request retained</p>}
      {data.fallback_contacts?.map((c,i)=><p key={i}>Fallback: {c.label} · {c.channel} · {c.contact}</p>)}
      {request?.status!=="RESOLVED"&&<form className="flex flex-col gap-3" onSubmit={e=>{e.preventDefault();void submit(!data.started);}}>
        {data.started&&<><label>Recorded action<select className="design-input w-full" value={action} onChange={e=>setAction(e.target.value)}>{actions.map(a=><option value={a} key={a}>{a.replaceAll("_"," ")}</option>)}</select></label>
          {["assign","handoff"].includes(action)&&<label>Responder<select className="design-input w-full" required value={responder} onChange={e=>setResponder(e.target.value)}><option value="">Choose staff within drill duty hours</option>{people.map(p=><option value={p.id} key={p.id}>{p.name} · #{p.id}</option>)}</select></label>}
          {action==="contact_attempt"&&<><label>Channel<select className="design-input w-full" value={channel} onChange={e=>setChannel(e.target.value)}>{["radio","phone","in_person"].map(c=><option key={c}>{c}</option>)}</select></label><label>Actual recorded outcome<select className="design-input w-full" value={outcome} onChange={e=>setOutcome(e.target.value)}>{["no_answer","connected","failed"].map(c=><option key={c}>{c}</option>)}</select></label></>}
          {action==="correlate"&&<label>Drill incident<select className="design-input w-full" required value={incident} onChange={e=>setIncident(e.target.value)}><option value="">Choose incident</option>{incidents.map(i=><option key={i.id} value={i.id}>{i.label} · DRILL-{i.id}</option>)}</select></label>}
          {action==="close"&&<label>Closure reason<select className="design-input w-full" value={closure} onChange={e=>setClosure(e.target.value)}>{["exercise_complete","assistance_completed","cancelled_by_resident","duplicate_correlated","unable_to_contact"].map(c=><option key={c}>{c}</option>)}</select></label>}
          <label>Action / dispatch / fallback evidence reference<input className="design-input w-full" maxLength={150} value={reference} onChange={e=>setReference(e.target.value)}/></label></>}
        <label>Action reason<input className="design-input w-full" required minLength={3} maxLength={500} value={reason} onChange={e=>setReason(e.target.value)}/></label>
        <button className="design-button" disabled={busy||blocked||!policy?.version}>{data.started?"Record drill action":"Start recorded response drill"}</button>
      </form>}
      {data.started&&<details><summary>Correlate requests without merging their histories</summary><label>New drill incident label<input className="design-input w-full" maxLength={120} value={incidentLabel} onChange={e=>setIncidentLabel(e.target.value)}/></label><p>Use the action reason above as the correlation reason. Then select the new incident in the correlate action.</p><button className="design-button" disabled={busy||blocked||incidentLabel.trim().length<3||reason.trim().length<3} onClick={()=>{setBusy(true);void accountRequest<{id:number;label:string}>("sos-response/incidents","POST",{label:incidentLabel,reason}).then(group=>{setIncidents(old=>[group,...old]);setIncident(String(group.id));setAction("correlate");setIncidentLabel("");}).catch(fail).finally(()=>setBusy(false));}}>Create drill incident</button></details>}
      <h4>Recorded response activity</h4>{data.events.map(e=><p key={e.id}>{sosTime(e.created_at)} · {e.message} {e.actor_name&&`(${e.actor_name})`}</p>)}
    </>}
    <details><summary>Operational activation remains unavailable</summary>{policy?.activation_requirements.map(r=><p key={r}>{r}</p>)}</details>
  </section>;
}
