"use client";
import { useCallback, useEffect, useState } from "react";
import { accountRequest } from "@/lib/accounts";
import { noticeKind, noticeLifecycle, parseNoticePage, type OfficialNotice } from "@/lib/notices";
import { alertTime } from "@/lib/alerts";

type Capabilities = { authorities: { id: string; name: string; authority_class: string; grant: { area_ids: string[] } }[]; areas: { id: string; name: string }[] };
export default function OfficialNotices() {
  const [items,setItems]=useState<OfficialNotice[]>([]),[caps,setCaps]=useState<Capabilities>({authorities:[],areas:[]});
  const [error,setError]=useState(""),[busy,setBusy]=useState(false),[offset,setOffset]=useState(0),[now,setNow]=useState(0);
  const [draft,setDraft]=useState<Partial<OfficialNotice>>({message_type:"Alert",status:"Test",category:"advisory",urgency:"Unknown",severity:"Unknown",certainty:"Unknown",area_ids:[]});
  const [editing,setEditing]=useState(false),[writeError,setWriteError]=useState("");
  const refresh=useCallback(async(signal?:AbortSignal)=>{
    try {
      const [page,permissions]=await Promise.all([
        accountRequest<{items:OfficialNotice[]}>(`official-notices?limit=50&offset=${offset}`,"GET",undefined,signal),
        accountRequest<Capabilities>("alert-governance/capabilities","GET",undefined,signal),
      ]);
      if(signal?.aborted)return;
      setItems(parseNoticePage(page));setCaps(permissions);setError("");
    } catch { if(!signal?.aborted){setItems([]);setError("Notice service unavailable; current official notices cannot be confirmed.");} }
  },[offset]);
  useEffect(()=>{const controller=new AbortController();void refresh(controller.signal);const poll=window.setInterval(()=>void refresh(controller.signal),30000);return()=>{controller.abort();clearInterval(poll);};},[refresh]);
  useEffect(()=>{setNow(Date.now());const timer=window.setInterval(()=>setNow(Date.now()),1000);return()=>clearInterval(timer);},[]);
  const authority=caps.authorities.find(a=>a.id===draft.authority_id);
  const set=(key:keyof OfficialNotice,value:unknown)=>setDraft(previous=>({...previous,[key]:value}));
  async function publish(event:React.FormEvent<HTMLFormElement>){
    event.preventDefault();setBusy(true);setWriteError("");
    try {
      await accountRequest("official-notices","POST",{
        authority_id:draft.authority_id,area_ids:draft.area_ids,message_type:draft.message_type,
        reference_id:draft.reference_id??null,status:draft.status,category:draft.category,
        urgency:draft.urgency,severity:draft.severity,certainty:draft.certainty,
        headline:draft.headline,instruction:draft.instruction,reason:draft.reason,
        effective_at:draft.effective_at?new Date(draft.effective_at).toISOString():new Date().toISOString(),
        expires_at:new Date(draft.expires_at??"").toISOString(),
      });setEditing(false);await refresh();
    }catch(reason){setWriteError(reason instanceof Error?reason.message:"Notice was not issued. Refresh and review before retrying.");}
    finally{setBusy(false);}
  }
  function revise(notice:OfficialNotice,kind:"Update"|"Cancel"){
    setDraft({...notice,message_type:kind,reference_id:notice.id,effective_at:"",expires_at:"",reason:""});setEditing(true);setWriteError("");
  }
  return <section className="design-panel p-4" aria-label="Authority notices">
    <div className="design-toolbar"><h2>App advisories and authority notices</h2><button className="design-button" onClick={()=>void refresh()}>Refresh notices</button>{caps.authorities.length>0&&<button className="design-button" onClick={()=>{setEditing(!editing);setDraft({message_type:"Alert",status:"Test",category:"advisory",urgency:"Unknown",severity:"Unknown",certainty:"Unknown",area_ids:[]});}}>Compose notice</button>}</div>
    <p className="subtle-note">Sensor observations and forecasts do not issue evacuation orders. Authority notices identify their issuer, area and validity.</p>
    {error?<p role="status">{error}</p>:!items.length?<p>No notices on this page. Absence of a notice does not establish safety.</p>:items.map(notice=><OfficialNoticeCard key={notice.id} notice={notice} now={now} onRevise={caps.authorities.some(a=>a.id===notice.authority_id)?revise:undefined}/>)}
    <div className="design-toolbar"><button className="design-button" disabled={!offset} onClick={()=>setOffset(value=>Math.max(0,value-50))}>Previous notices</button><span>{items.length?`${offset+1}–${offset+items.length}`:"0 notices"}</span><button className="design-button" disabled={items.length<50} onClick={()=>setOffset(value=>value+50)}>Next notices</button></div>
    {editing&&<form onSubmit={publish} className="grid gap-3 mt-3">
      <h3>{draft.message_type} notice · issuer and jurisdiction required</h3>
      <label>Issuing authority<select className="design-input" required value={draft.authority_id??""} onChange={e=>{set("authority_id",e.target.value);set("area_ids",[]);set("category","advisory");}} disabled={draft.message_type!=="Alert"}><option value="">Choose authorized issuer</option>{caps.authorities.map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select></label>
      <label>Affected areas<select className="design-input" required multiple value={draft.area_ids??[]} onChange={e=>set("area_ids",Array.from(e.target.selectedOptions,option=>option.value))}>{caps.areas.filter(a=>authority?.grant.area_ids.includes(a.id)).map(a=><option key={a.id} value={a.id}>{a.name} · {a.id}</option>)}</select></label>
      <label>Status<select className="design-input" value={draft.status} disabled={draft.message_type!=="Alert"} onChange={e=>set("status",e.target.value)}>{["Test","Exercise","Actual"].map(value=><option key={value}>{value}</option>)}</select></label>
      <label>Message category<select className="design-input" value={draft.category} onChange={e=>set("category",e.target.value)}><option value="advisory">Advisory</option>{authority?.authority_class==="public_authority"&&<option value="action">Authority-issued action</option>}</select></label>
      {([['urgency',['Unknown','Immediate','Expected','Future','Past']],['severity',['Unknown','Minor','Moderate','Severe','Extreme']],['certainty',['Unknown','Observed','Likely','Possible','Unlikely']]] as const).map(([key,values])=><label key={key}>{key}<select className="design-input" value={draft[key]} onChange={e=>set(key,e.target.value)}>{values.map(value=><option key={value}>{value}</option>)}</select></label>)}
      <label>Headline<input className="design-input" required minLength={5} maxLength={200} value={draft.headline??""} onChange={e=>set("headline",e.target.value)}/></label>
      <label>Instructions<textarea className="design-input" required minLength={10} maxLength={4000} value={draft.instruction??""} onChange={e=>set("instruction",e.target.value)}/></label>
      <label>Issue/correction/cancellation reason<input className="design-input" required minLength={10} maxLength={1000} value={draft.reason??""} onChange={e=>set("reason",e.target.value)}/></label>
      <label>Effective time (local; blank means now)<input className="design-input" type="datetime-local" value={draft.effective_at??""} onChange={e=>set("effective_at",e.target.value)}/></label>
      <label>Expiry (local)<input className="design-input" required type="datetime-local" value={draft.expires_at??""} onChange={e=>set("expires_at",e.target.value)}/></label>
      <p>Issuing as {authority?.name??"no issuer selected"} · {draft.status} · {draft.category}. This publishes an in-app notice; it does not send a citywide push.</p>
      {writeError&&<p role="alert">{writeError}</p>}<button className="design-button" disabled={busy||!authority}>{busy?"Issuing…":`Issue ${draft.message_type} notice`}</button>
    </form>}
  </section>;
}


export function OfficialNoticeCard({notice,now,onRevise}:{notice:OfficialNotice;now:number;onRevise?:(notice:OfficialNotice,kind:"Update"|"Cancel")=>void}) {
  return <article className="p-3">
      <strong>{notice.status!=="Actual"?`${notice.status.toUpperCase()} · `:""}{noticeKind(notice)} · {noticeLifecycle(notice,now)}</strong>
      <h3>{notice.headline}</h3><p>{notice.instruction}</p>
      <p className="subtle-note">Issuer: {notice.issuer_name} ({notice.authority_id}) · Areas: {notice.area_names.join(", ")} ({notice.area_ids.join(", ")})</p>
      <p className="subtle-note">Issued {alertTime(notice.sent_at)} · Effective {alertTime(notice.effective_at)} · Expires {alertTime(notice.expires_at)}</p>
      <p className="subtle-note">{notice.urgency} urgency · {notice.severity} severity · {notice.certainty} certainty · {notice.message_type} · ID {notice.id}{notice.reference_id?` · References ${notice.reference_id}`:""}{notice.superseded_by?` · Replaced by ${notice.superseded_by}`:""}</p>
      {onRevise&&!notice.superseded_by&&notice.message_type!=="Cancel"&&<div><button className="design-button" onClick={()=>onRevise(notice,"Update")}>Correct notice</button><button className="design-button" onClick={()=>onRevise(notice,"Cancel")}>Cancel notice</button></div>}
    </article>;
}
