"use client";
import {useCallback,useEffect,useState,useRef} from "react";
import {useAccount} from "@/context/AccountContext";
import {accountRequest} from "@/lib/accounts";
import {useEvidenceClock} from "@/hooks/useEvidenceClock";
import {evidenceIsCurrent} from "@/lib/operations-console";
import {visiblePoll} from "@/lib/visible-poll";

type Receipt={stage:string;basis:string;recorded_at:string;attempt_no:number};
type Delivery={id:number;alert_id:number;station_id:string;severity:string;state:string;version:number;queued_at:string;expires_at:string;expired:boolean;
  review_status:string;review_required:boolean;provider_accepted:boolean;operator_attested_acceptance:boolean;conflicting_evidence:boolean;receipt_stages:Receipt[];
  attempts:{attempt_no:number;outcome:string;provider_reference:string|null}[];reviews:{id:number;decision:string;reason:string;evidence_sha256:string;created_at:string}[]};
type Page={items:Delivery[];next_before_id:number|null;checked_at:string;scope:string};
export default function DeliveryConsole(){
  const {user}=useAccount();const [page,setPage]=useState<Page|null>(null),[error,setError]=useState("");
  const [filter,setFilter]=useState(""),[before,setBefore]=useState<number|null>(null);
  const [selected,setSelected]=useState<Delivery|null>(null),[blocked,setBlocked]=useState(false),[busy,setBusy]=useState(false);
  const [reason,setReason]=useState(""),[reference,setReference]=useState(""),[decision,setDecision]=useState("closed_no_resend");
  const generation=useRef(0);
  const refresh=useCallback(async(signal?:AbortSignal)=>{
    const ticket=++generation.current;
    const query=new URLSearchParams({limit:"30"});if(filter)query.set("state",filter);if(before)query.set("before_id",String(before));
    try{const next=await accountRequest<Page>(`notification-deliveries?${query}`,"GET",undefined,signal);if(!signal?.aborted&&ticket===generation.current){setPage(next);setError("");}}
    catch(error){if(!signal?.aborted&&ticket===generation.current)setError(error instanceof Error?error.message:"Delivery evidence unavailable");throw error;}
  },[filter,before]);
  useEffect(()=>visiblePoll(refresh,15000),[refresh]);
  const newer=selected&&page?.items.find(row=>row.id===selected.id)?.version!==selected.version;
  const now=useEvidenceClock(),known=Boolean(page&&evidenceIsCurrent(page.checked_at,now)&&!error);
  const locked=busy||blocked||Boolean(newer)||!known;
  function review(row:Delivery){setSelected(structuredClone(row));setBlocked(false);setReason("");setReference("");setDecision("closed_no_resend");}
  async function submit(){
    if(!selected||locked||reason.trim().length<8||!reference.trim())return;
    setBusy(true);
    try{
      const hash=Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256",new TextEncoder().encode(reference.trim())))).map(b=>b.toString(16).padStart(2,"0")).join("");
      const updated=await accountRequest<Delivery>(`notification-deliveries/${selected.id}/reconcile`,"POST",{
        expected_version:selected.version,decision,reason:reason.trim(),evidence_sha256:hash,
        evidence_kind:["provider_accepted","not_accepted"].includes(decision)?"provider_record":decision==="followup_recorded"?"fallback_action":"manual_review",
      });
      setSelected(null);setReason("");setReference("");setPage(old=>old&&({...old,items:old.items.map(row=>row.id===updated.id?updated:row)}));
    }catch(error){setError(error instanceof Error?error.message:"Reconciliation failed");setBlocked(true);setReason("");setReference("");}
    finally{setBusy(false);}
  }
  return <section className="design-panel p-4 flex flex-col gap-3" aria-label="Notification delivery evidence">
    <h2>Notification delivery evidence</h2>
    <p className="subtle-note">Queued, provider accepted, app received, opened and user acknowledged are separate stages. Missing callbacks mean unknown. No stage confirms evacuation or responder dispatch.</p>
    <div className="flex flex-wrap gap-2"><label>Transport state <select className="design-input" value={filter} onChange={event=>{setPage(null);setFilter(event.target.value);setBefore(null);setSelected(null);}}><option value="">All</option>{["PENDING","PROCESSING","UNKNOWN","SENT","FAILED","SUPPRESSED","TESTED"].map(state=><option key={state}>{state}</option>)}</select></label>
      <button className="design-button" onClick={()=>{setPage(null);setSelected(null);setBlocked(false);void refresh().catch(()=>{});}}>Refresh and review deliveries</button>
      {before&&<button className="design-button" onClick={()=>{setPage(null);setBefore(null);setSelected(null);}}>Newest</button>}
    </div>
    {error&&<p role="status">{error} Last-loaded evidence may be stale.</p>}
    <p className="subtle-note">{!known&&page&&"Last-known evidence; refresh before review. "}{page?`${page.items.length} shown · ${page.scope} · checked ${page.checked_at}`:"Waiting for authorized delivery evidence"}</p>
    <div className="overflow-x-auto"><table className="w-full"><thead><tr>{["Delivery / station","Transport","Provider evidence","App callbacks","Review"].map(name=><th className="p-2 text-left" key={name}>{name}</th>)}</tr></thead><tbody>{page?.items.map(row=><tr key={row.id}>
      <td className="p-2">#{row.id} · {row.station_id}<p>{row.severity} · alert #{row.alert_id}</p><p className="subtle-note">Queued {row.queued_at} · expires {row.expires_at}{row.expired||Date.parse(row.expires_at)<=now?" · expired":""}</p></td>
      <td className="p-2">{row.state}{row.review_required&&<p>Review required; no automatic reclaim</p>}</td>
      <td className="p-2">{row.provider_accepted?"Provider accepted":"Acceptance unconfirmed"}{row.operator_attested_acceptance&&<p>Operator-attested acceptance; see evidence digest</p>}{row.conflicting_evidence&&<p role="alert">Conflicting provider/review evidence</p>}{row.attempts.map(attempt=><p className="subtle-note break-all" key={attempt.attempt_no}>Attempt {attempt.attempt_no}: {attempt.outcome} · {attempt.provider_reference??"No provider reference"}</p>)}</td>
      <td className="p-2">{["RECEIVED","OPENED","ACKNOWLEDGED"].map(stage=>{const found=row.receipt_stages.filter(item=>item.stage===stage);return <p key={stage}>{stage}: {found.length?found.map(item=>`${item.recorded_at} (${item.basis})`).join(", "):"unknown / not instrumented"}</p>;})}</td>
      <td className="p-2">{row.review_status}{user.role==="admin"&&<button className="design-button" disabled={!known||busy} onClick={()=>review(row)}>Review evidence #{row.id}</button>}</td>
    </tr>)}</tbody></table></div>
    {page&&!page.items.length&&<p>No deliveries in this authorized scope and state. This is not a platform-wide delivery count.</p>}
    {page?.next_before_id&&<button className="design-button" onClick={()=>{setPage(null);setBefore(page.next_before_id);setSelected(null);}}>Older deliveries</button>}
    {selected&&<form className="flex flex-col gap-2" onSubmit={event=>{event.preventDefault();void submit();}}>
      <h3>Review delivery #{selected.id} · captured version {selected.version}</h3>
      <p>This records your evidence and stops automatic future attempts for this delivery. It never resends or resets UNKNOWN to pending. Provider acceptance decisions require an actual provider record. Fallback actions must already have occurred under your approved response procedure.</p>
      {(blocked||newer)&&<p role="alert">Evidence changed. Refresh and review manually before taking another action.</p>}
      <label>Decision <select className="design-input" value={decision} disabled={locked} onChange={event=>setDecision(event.target.value)}><option value="closed_no_resend">Close without resend</option><option value="provider_accepted">Operator confirms provider acceptance</option><option value="not_accepted">Operator confirms provider rejection</option><option value="followup_recorded">Record completed fallback/contact action</option></select></label>
      <label>Review reason <textarea className="design-input" value={reason} disabled={locked} minLength={8} maxLength={500} onChange={event=>setReason(event.target.value)}/></label>
      <label>External evidence reference (only SHA-256 is retained) <input className="design-input" value={reference} disabled={locked} maxLength={256} onChange={event=>setReference(event.target.value)}/></label>
      <button className="design-button" disabled={locked||reason.trim().length<8||!reference.trim()}>Record reviewed decision</button>
      <div>{selected.reviews.map(row=><p key={row.id}>{row.created_at} · {row.decision} · {row.reason} · evidence SHA-256 {row.evidence_sha256}</p>)}</div>
    </form>}
    <p className="subtle-note">Fallback channels are manual, operator-recorded actions. SMS, calls, radio and sirens are not sent by this console. Use verified operational contacts and consent/jurisdiction procedures.</p>
  </section>;
}
