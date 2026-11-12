"use client";
import {useState} from 'react';
import Link from 'next/link';
import {useAccount} from '@/context/AccountContext';
import {accountRequest} from '@/lib/accounts';
import {alertTime} from '@/lib/alerts';
import {agedWorkerState,latencyBound,type OperationalDiagnostics} from '@/lib/operations-console';

function RecoveryReviewTools({report,known}:{report:OperationalDiagnostics;known:boolean}){
  const {user}=useAccount();
  const [capture,setCapture]=useState<{checked_at:string;codes:string[]}|null>(null),[code,setCode]=useState('GENERAL_REVIEW');
  const [activity,setActivity]=useState('investigated'),[reason,setReason]=useState(''),[reference,setReference]=useState('');
  const [busy,setBusy]=useState(false),[blocked,setBlocked]=useState(false),[message,setMessage]=useState('');
  function review(){setCapture({checked_at:report.checked_at,codes:report.alerts.map(a=>a.code)});setCode(report.alerts[0]?.code??'GENERAL_REVIEW');setReason('');setReference('');setBlocked(false);setMessage('');}
  async function submit(){
    if(!capture||busy||blocked||reason.trim().length<8||!reference.trim())return;
    setBusy(true);setMessage('');
    try{const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(reference.trim()));
      const evidence_sha256=Array.from(new Uint8Array(bytes)).map(v=>v.toString(16).padStart(2,'0')).join('');
      const result=await accountRequest<{id:number;recorded_at:string;notice:string}>('operations/recovery-reviews','POST',{checked_at:capture.checked_at,code,activity,reason:reason.trim(),evidence_sha256});
      setMessage(`Review #${result.id} recorded ${alertTime(result.recorded_at)}. ${result.notice}`);setReference('');setReason('');
    }catch(error){setMessage(error instanceof Error?error.message:'Review receipt is unconfirmed. Refresh before another action.');}
    finally{setBusy(false);setBlocked(true);}
  }
  return <section className="design-panel p-4"><h2>Reconciliation and recovery tools</h2>
    <p>Delivery reconciliation below records evidence without resending. Recovery reviews record an operator attestation; they do not clear a fault, restart a worker or release restored data.</p>
    <details><summary>Guided fault investigation and recovery</summary><ol className="recovery-steps"><li>Capture the checked time and fault code. Inspect ingress, dependencies and the worker's last successful progress; preserve original observation times.</li><li>For an uncertain or stuck send, inspect provider and app-stage evidence. Use the delivery's versioned review; never reset UNKNOWN or PROCESSING to pending.</li><li>Use the approved service supervisor or restore procedure outside this console. A restored database stays quarantined until its data and historical sends are reconciled.</li><li>Verify a new dependency observation and a controlled resident receipt where authorized. Record a handoff or completed review with its external evidence reference.</li></ol></details>
    <Link href="/settings">Account, privacy and deployment evidence</Link>
    {user.role==='admin'?<><button className="design-button" disabled={!known||busy} onClick={review}>Capture diagnostic review</button>{capture&&<form className="recovery-review-form" onSubmit={e=>{e.preventDefault();void submit();}}><h3>Captured diagnostics {alertTime(capture.checked_at)}</h3>
      <label>Fault / review scope<select className="design-input" value={code} disabled={busy||blocked} onChange={e=>{setCode(e.target.value);setReason('');setReference('');}}>{Array.from(new Set([...capture.codes,'GENERAL_REVIEW'])).map(value=><option key={value}>{value}</option>)}</select></label>
      <label>Completed activity<select className="design-input" value={activity} disabled={busy||blocked} onChange={e=>setActivity(e.target.value)}><option value="investigated">Investigation recorded</option><option value="handoff_recorded">Completed handoff recorded</option><option value="completed_recovery_review">Completed recovery review recorded</option></select></label>
      <label>Recovery review reason<textarea className="design-input" minLength={8} maxLength={500} value={reason} disabled={busy||blocked} onChange={e=>setReason(e.target.value)}/></label>
      <label>Recovery evidence reference (only SHA-256 is retained)<input className="design-input" maxLength={256} value={reference} disabled={busy||blocked} onChange={e=>setReference(e.target.value)}/></label>
      <button className="design-button" disabled={busy||blocked||reason.trim().length<8||!reference.trim()}>{busy?'Recording…':'Record recovery review'}</button>
      {blocked&&<p>Capture fresh diagnostics and manually review before another submission. No automatic retry occurred.</p>}
    </form>}{message&&<p role="status">{message}</p>}</>:<p className="subtle-note">Administrator access is required to append a recovery review. Read-only diagnostics and authorized delivery evidence remain available.</p>}
  </section>;
}

export default function OperationsDetails({report,known,now}:{report:OperationalDiagnostics;known:boolean;now:number}){
  const queue=report.components.find(c=>c.name==='notifications');
  const elapsed=Math.max(0,(now-Date.parse(report.checked_at))/1000);
  const count=(value:number|undefined)=>value==null?'—':`${value}${known?'':' (last reported)'}`;
  return <>
    <section className="design-panel p-4"><h2>Resident delivery pipeline</h2><p className="subtle-note">Platform-wide unresolved queue aggregates. Delivery details below follow your authorized jurisdiction. Provider acceptance, app receipt, opened and acknowledgement are independent evidence stages.</p>
      <dl className="operations-metrics">{[['Queued',queue?.pending],['Processing',queue?.processing],['Stalled processing',queue?.stalled],['Uncertain',queue?.uncertain],['Failed / unreviewed',queue?.failed]].map(([label,value])=><div key={label}><dt>{label}</dt><dd>{count(value as number|undefined)}</dd></div>)}</dl>
      <p>Oldest pending: {queue?.pending===0?'No pending deliveries':queue?.oldest_pending_seconds==null?'unknown':`${Math.floor(queue.oldest_pending_seconds+elapsed)}s since queued`} · oldest processing at check: {queue?.oldest_processing_seconds==null?'unknown':`${Math.floor(queue.oldest_processing_seconds)}s`} · queue budget {queue?.queue_budget_seconds??'unknown'}s</p>
      <p>Transport configuration: {queue?.provider_mode??'unknown'}. A configured provider is not proof of phone receipt.</p>
    </section>
    <div className="staff-overview-grid"><section className="design-panel p-4"><h2>Ingress progress</h2><p>{report.ingress?`${count(report.ingress.stale_or_missing_eligible_receipt_count)} of ${report.ingress.stations_checked} checked active station(s) lack an eligible water-packet receipt within ${report.ingress.receipt_budget_seconds}s`:'Ingress progress evidence unavailable'}</p><p className="subtle-note">This measures eligible packet receipt. It does not date the last valid depth or prove rain operation. Inspect the independent station channels for measurement quality.</p>{report.ingress?.bounded&&<p role="alert">Station budget exceeded; this diagnostic view is bounded and incomplete.</p>}</section>
      <section className="design-panel p-4"><h2>Quotas and capacity evidence</h2><p className="subtle-note">Local configured budgets and external provider capacity are different evidence.</p><ul>{(report.external_quotas??[{service:'External providers',state:'unknown',reason:'Quota telemetry is unavailable'}]).map(item=><li key={item.service}><strong>{item.service}: {item.state}</strong><p>{item.reason}</p></li>)}</ul>
        <p>Local budgets: {report.budgets?`${report.budgets.station_limit} stations; water ${report.budgets.water_attempts_per_station_minute} attempts/station/min; rain ${report.budgets.rain_attempts_per_station_minute} attempts/station/min`:'unavailable'}</p></section></div>
    <section className="design-panel p-4"><h2>Worker liveness and progress</h2><div className="design-table-wrap"><table className="design-table"><caption>Observed worker heartbeats; current health expires after 45 seconds</caption><thead><tr><th>Worker</th><th>State now</th><th>Last heartbeat (PHT)</th><th>Last successful progress (PHT)</th></tr></thead><tbody>{report.workers?.map(worker=><tr key={worker.role}><td>{worker.role}</td><td>{agedWorkerState(worker,report.checked_at,now,known)}</td><td>{alertTime(worker.observed_at)}</td><td>{alertTime(worker.last_success_at)}</td></tr>)}</tbody></table></div>{!report.workers?.length&&<p>No worker heartbeat evidence recorded. This is not proof of a healthy worker.</p>}</section>
    <section className="design-panel p-4"><h2>Workflow latency and failures</h2><p className="subtle-note">{report.metrics_window_minutes??'Unknown'} minute telemetry window. Histogram bounds are not exact percentiles. No observations stays unknown; HTTP success does not prove resident receipt.</p>
      <div className="design-table-wrap"><table className="design-table"><caption>Observed workflow durations and failures</caption><thead><tr><th>Workflow</th><th>Events</th><th>Failures</th><th>p95 bucket bound</th><th>p99 bucket bound</th><th>Maximum seconds</th></tr></thead><tbody>{Object.entries(report.metrics??{}).filter(([key])=>key!=='http.queries').map(([key,row])=><tr key={key}><td>{key}</td><td>{row.count}</td><td>{row.failures}</td><td>{latencyBound(row.p95_seconds_upper_bound,row.count)}</td><td>{latencyBound(row.p99_seconds_upper_bound,row.count)}</td><td>{row.count?row.maximum_seconds.toFixed(3):'—'}</td></tr>)}</tbody></table></div>
      {!Object.keys(report.metrics??{}).length&&<p>No duration metrics recorded in this window.</p>}<a className="design-button" download="agapay-diagnostic-evidence.json" href={'data:application/json;charset=utf-8,'+encodeURIComponent(JSON.stringify(report,null,2))}>Download captured diagnostic evidence</a>
    </section><RecoveryReviewTools report={report} known={known}/>
  </>;
}
