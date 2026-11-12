"use client";
import {useEffect,useRef,useState} from "react";
import {accountRequest,AccountError} from "@/lib/accounts";

type Row={id:string;kind:string;authority_id:string;mode:string;area_ids:string[];version:number;data:Record<string,unknown>;source:string;verification:string;effective_state:string;issuer_name:string;verified_at:string|null;expires_at:string|null;route_safety:string};
type Context={authorities:{id:string;name:string;authority_class:string;area_ids:string[]}[];areas:{id:string;name:string;area_class:string}[]};
type Draft={id:string;authority_id:string;area_ids:string[];name:string;source:string;address:string;latitude:string;longitude:string;state:string;activated_at:string;capacity:string;occupancy:string;capacity_observed_at:string;wheelchair:string;services:string;constraints:string;instructions:string;contacts:string;geometry:string};
const empty:Draft={id:"",authority_id:"",area_ids:[],name:"",source:"",address:"",latitude:"",longitude:"",state:"inactive",activated_at:"",capacity:"",occupancy:"",capacity_observed_at:"",wheelchair:"unknown",services:"",constraints:"",instructions:"",contacts:"",geometry:""};
function utcInput(value:unknown){return value?new Date(String(value)).toISOString().slice(0,16):"";}
function fromRow(row:Row):Draft{
  const d=row.data,p=d.point as {latitude:number;longitude:number}|undefined;
  return {...empty,id:row.id,authority_id:row.authority_id,area_ids:row.area_ids,name:String(d.name),source:row.source,address:String(d.address??""),latitude:p?String(p.latitude):"",longitude:p?String(p.longitude):"",state:String(d.state??"inactive"),activated_at:utcInput(d.activated_at),capacity:String(d.capacity??""),occupancy:String(d.occupancy??""),capacity_observed_at:utcInput(d.capacity_observed_at),wheelchair:d.wheelchair_accessible==null?"unknown":String(d.wheelchair_accessible),services:(d.services as string[]|undefined)?.join(", ")??"",constraints:String(d.access_constraints??""),instructions:String(d.instructions??""),contacts:(d.contacts as {name:string;contact:string;hours:string}[]).map(c=>`${c.name} | ${c.contact} | ${c.hours}`).join("\n"),geometry:(d.geometry as {latitude:number;longitude:number}[]|undefined)?.map(p=>`${p.latitude}, ${p.longitude}`).join("\n")??""};
}
export function resourceVerification(row:Row,now=Date.now()){
  return row.verification==="verified"&&(!row.expires_at||Date.parse(row.expires_at)<=now)?"expired":row.verification;
}
export default function ResponseResources(){
  const [context,setContext]=useState<Context|null>(null),[rows,setRows]=useState<Row[]>([]),[kind,setKind]=useState("shelter"),[mode,setMode]=useState("Actual"),[offset,setOffset]=useState(0),[total,setTotal]=useState(0);
  const [selected,setSelected]=useState<Row|null>(null),[draft,setDraft]=useState<Draft>({...empty}),[reason,setReason]=useState(""),[expiry,setExpiry]=useState(""),[dirty,setDirty]=useState(true),[blocked,setBlocked]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState(""),[history,setHistory]=useState<unknown[]>([]);
  const generation=useRef(0);
  const [clock,setClock]=useState(0);
  useEffect(()=>{const timer=setInterval(()=>setClock(Date.now()),1000);setClock(Date.now());return()=>clearInterval(timer);},[]);
  function discard(){setSelected(null);setDraft({...empty,state:kind==="road"?"closed":"inactive"});setReason("");setExpiry("");setDirty(true);setHistory([]);}
  function failure(e:unknown){setError(e instanceof Error?e.message:"Action not confirmed");if(!(e instanceof AccountError&&e.status===422)){discard();setBlocked(true);}}
  async function load(){const request=++generation.current;setBusy(true);setBlocked(true);setRows([]);discard();try{const [page,ctx]=await Promise.all([accountRequest<{items:Row[];total:number}>(`response-resources?kind=${kind}&mode=${mode}&include_drafts=true&limit=50&offset=${offset}`),accountRequest<Context>("response-resources/maintenance-context")]);if(request!==generation.current)return;setRows(page.items);setTotal(page.total);setContext(ctx);setBlocked(false);setError("");discard();}catch(e){if(request===generation.current)failure(e);}finally{if(request===generation.current)setBusy(false);}}
  useEffect(()=>{void load();return()=>{generation.current++;};},[kind,mode,offset]);
  function field<K extends keyof Draft>(key:K,value:Draft[K]){setDraft(old=>({...old,[key]:value}));setDirty(true);}
  function choose(row:Row){if(blocked)return;setSelected(row);setDraft(fromRow(row));setReason("");setExpiry("");setDirty(false);setHistory([]);}
  function body(){
    const contacts=draft.contacts.split("\n").filter(Boolean).map(line=>{const [name,contact,hours,...extra]=line.split("|").map(s=>s.trim());if(!name||!contact||!hours||extra.length)throw new Error("Each contact needs Name | Contact | Hours");return{name,contact,hours};});
    const data:Record<string,unknown>={name:draft.name,instructions:draft.instructions,contacts};
    if(kind!=="preparedness")data.access_constraints=draft.constraints;
    if(kind==="shelter")Object.assign(data,{address:draft.address,point:{latitude:Number(draft.latitude),longitude:Number(draft.longitude)},state:draft.state,activated_at:draft.activated_at?draft.activated_at+":00Z":null,capacity:draft.capacity===""?null:Number(draft.capacity),occupancy:draft.occupancy===""?null:Number(draft.occupancy),capacity_observed_at:draft.capacity_observed_at?draft.capacity_observed_at+":00Z":null,wheelchair_accessible:draft.wheelchair==="unknown"?null:draft.wheelchair==="true",services:draft.services.split(",").map(s=>s.trim()).filter(Boolean)});
    if(kind==="road")Object.assign(data,{state:draft.state,geometry:draft.geometry.split("\n").filter(Boolean).map(line=>{const pair=line.split(",").map(Number);if(pair.length!==2||pair.some(v=>!Number.isFinite(v)))throw new Error("Each road point needs latitude, longitude");return{latitude:pair[0],longitude:pair[1]};})});
    return data;
  }
  async function save(){
    if(busy||blocked)return;let data:Record<string,unknown>;
    try{data=body();}catch(e){setError(e instanceof Error?e.message:"Invalid fields");return;}
    const id=draft.id||crypto.randomUUID();setDraft(old=>({...old,id}));setBusy(true);setError("");
    try{const row=await accountRequest<Row>("response-resources","POST",{id,kind,mode,authority_id:draft.authority_id,area_ids:draft.area_ids,expected_version:selected?.version??0,source:draft.source,reason,data});setSelected(row);setDraft(fromRow(row));setDirty(false);setReason("");setRows(old=>[row,...old.filter(r=>r.id!==row.id)]);}
    catch(e){failure(e);}finally{setBusy(false);}
  }
  async function review(action:string){
    if(!selected||dirty||busy||blocked)return;setBusy(true);setError("");
    try{const row=await accountRequest<Row>(`response-resources/${selected.id}/review`,"POST",{expected_version:selected.version,action,reason,...(action==="verify"?{expires_at:expiry+":00Z"}:{})});setSelected(row);setDraft(fromRow(row));setReason("");setRows(old=>old.map(r=>r.id===row.id?row:r));}
    catch(e){failure(e);}finally{setBusy(false);}
  }
  const authority=context?.authorities.find(a=>a.id===draft.authority_id);
  const input=(label:string,key:keyof Draft,type="text",required=false)=><label>{label}<input className="design-input w-full" type={type} step={type==="number"?"any":undefined} required={required} value={String(draft[key])} onChange={e=>field(key,e.target.value as never)}/></label>;
  return <div className="design-page flex flex-col gap-4"><h2>Response resource registry</h2><p className="subtle-note">No live shelter, closure or preparedness reference is prefilled. Records require source evidence, authorized jurisdiction and a separate verification step. Generic directions never certify flood-safe access.</p>
    <div className="design-toolbar"><select aria-label="Resource kind" className="design-input" value={kind} disabled={busy} onChange={e=>{setKind(e.target.value);setOffset(0);}}>{["shelter","road","preparedness"].map(v=><option key={v}>{v}</option>)}</select><select aria-label="Resource namespace" className="design-input" value={mode} disabled={busy} onChange={e=>{setMode(e.target.value);setOffset(0);}}><option>Actual</option><option>Exercise</option></select><button className="design-button" disabled={busy} onClick={()=>void load()}>Refresh and review registry</button><button className="design-button" disabled={busy||blocked} onClick={discard}>New draft</button></div>
    {error&&<p role="alert">{error}</p>}{blocked&&<p>Inputs discarded. Writes are blocked until an explicit successful refresh.</p>}
    <div className="design-table-wrap"><table className="design-table"><thead><tr>{["Name","Source","Verification","State","Expires","Action"].map(v=><th key={v}>{v}</th>)}</tr></thead><tbody>{rows.map(r=><tr key={r.id}><td>{String(r.data.name)}</td><td>{r.issuer_name}<small>{r.source}</small></td><td>{resourceVerification(r,clock)}</td><td>{r.effective_state}</td><td>{r.expires_at??"not verified"}</td><td><button className="design-button" disabled={blocked||busy} onClick={()=>choose(r)}>Review record</button></td></tr>)}{!rows.length&&<tr><td colSpan={6}>No records in this namespace. No demonstration destination is substituted.</td></tr>}</tbody></table></div>
    <div className="flex gap-2"><button className="design-button" disabled={offset===0||busy} onClick={()=>setOffset(v=>Math.max(0,v-50))}>Previous</button><span>{rows.length} shown · {total} records</span><button className="design-button" disabled={offset+50>=total||busy} onClick={()=>setOffset(v=>v+50)}>Next</button></div>
    {!context?.authorities.length?<p>Configure an active authority grant and verified area jurisdiction before maintaining resources. Actual records require a public authority; app-operator grants support exercises only.</p>:<form className="design-panel p-4 grid gap-3" onSubmit={e=>{e.preventDefault();void save();}}>
      <h3>{selected?`${selected.id} · version ${selected.version}`:"New unverified draft"}</h3>
      <label>Issuing authority<select className="design-input w-full" required disabled={selected!==null} value={draft.authority_id} onChange={e=>{field("authority_id",e.target.value);field("area_ids",[]);}}><option value="">Select authority</option>{context.authorities.map(a=><option key={a.id} value={a.id}>{a.name} · {a.authority_class}</option>)}</select></label>
      <fieldset><legend>Verified area identifiers within the maintainer grant</legend>{context.areas.filter(a=>authority?.area_ids.includes(a.id)).map(a=><label className="mr-4" key={a.id}><input type="checkbox" checked={draft.area_ids.includes(a.id)} onChange={e=>field("area_ids",e.target.checked?[...draft.area_ids,a.id]:draft.area_ids.filter(v=>v!==a.id))}/>{a.name} · {a.id}</label>)}</fieldset>
      {input("Name","name","text",true)}{input("Evidence/source reference","source","text",true)}
      {kind==="shelter"&&<>{input("Address / entrance description","address","text",true)}<div className="grid grid-cols-2 gap-2">{input("Latitude","latitude","number",true)}{input("Longitude","longitude","number",true)}</div>{input("Activation time (UTC)","activated_at","datetime-local")}{input("Capacity (blank means unknown)","capacity","number")}{input("Occupancy (blank means unknown)","occupancy","number")}{input("Capacity observation time (UTC)","capacity_observed_at","datetime-local")}<label>Wheelchair access<select className="design-input w-full" value={draft.wheelchair} onChange={e=>field("wheelchair",e.target.value)}><option value="unknown">Unknown</option><option value="true">Reported available</option><option value="false">Reported unavailable</option></select></label>{input("Services (comma separated)","services")}</>}
      {kind!=="preparedness"&&<label>Reported state<select className="design-input w-full" value={draft.state} onChange={e=>field("state",e.target.value)}>{(kind==="shelter"?["inactive","active","full"]:["closed","restricted","reopened"]).map(v=><option key={v}>{v}</option>)}</select></label>}
      {kind==="road"&&<label>Road geometry · one latitude, longitude pair per line<textarea className="design-input w-full" required rows={4} value={draft.geometry} onChange={e=>field("geometry",e.target.value)}/></label>}
      {kind!=="preparedness"&&<label>Access constraints<textarea className="design-input w-full" required maxLength={2000} value={draft.constraints} onChange={e=>field("constraints",e.target.value)}/></label>}
      <label>Source instructions<textarea className="design-input w-full" required maxLength={2000} value={draft.instructions} onChange={e=>field("instructions",e.target.value)}/></label>
      <label>Contacts · one Name | Contact | Hours per line<textarea className="design-input w-full" required rows={3} value={draft.contacts} onChange={e=>field("contacts",e.target.value)}/></label>
      <label>Actor review/change reason<input className="design-input w-full" required minLength={3} maxLength={500} value={reason} onChange={e=>setReason(e.target.value)}/></label>
      <button className="design-button" disabled={busy||blocked||!dirty||!draft.area_ids.length}>Save unverified revision</button>
      {selected&&<><p>Save content edits before verification. Verification applies to the persisted revision shown above.</p><label>Verification expires (UTC)<input className="design-input w-full" type="datetime-local" value={expiry} onChange={e=>setExpiry(e.target.value)}/></label><div className="flex gap-2"><button type="button" className="design-button" disabled={busy||blocked||dirty||!expiry||reason.trim().length<3} onClick={()=>void review("verify")}>Verify this revision</button><button type="button" className="design-button danger" disabled={busy||blocked||dirty||reason.trim().length<3} onClick={()=>void review("withdraw")}>Withdraw this resource</button><button type="button" className="design-button" onClick={()=>void accountRequest<unknown[]>(`response-resources/${selected.id}/revisions`).then(setHistory).catch(failure)}>Read revision history</button></div>{history.map((h,i)=><pre className="whitespace-pre-wrap break-all" key={i}>{JSON.stringify(h,null,2)}</pre>)}</>}
    </form>}
  </div>;
}
