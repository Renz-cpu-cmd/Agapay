"use client";
import {useEffect,useRef,useState} from 'react';
import {useAccount} from '@/context/AccountContext';
import {useMonitoring} from '@/context/MonitoringContext';
import {accountRequest} from '@/lib/accounts';
import DecisionEvaluation,{type DecisionReport} from './DecisionEvaluation';
type Score={count:number;mae_cm:number;rmse_cm:number;bias_cm:number;maximum_absolute_error_cm:number};
export type Candidate={id:string;version:number;state:string;card:{station_id:string;datum:string;configuration_hash:string;source_class:string;data_license:string;provenance:string;calibration_history:string;training_cutoff:string;features:string;limitations:string;allowed_use:string;fallback:string};evaluation:Record<string,Record<string,Score>>;decision_evaluation?:DecisionReport};
type RainScore={mae_mm:number|null;rmse_mm:number|null;count:number};
export type Catalog={checked_at?:string;operational:Candidate[];experimental:{status:string;reason?:string;model_version?:string;source?:string;training_cutoff?:string;artifact_sha256?:string;evaluation_sha256?:string;notice?:string;evaluation?:{test:Record<string,{overall:RainScore;by_horizon?:Record<string,{overall:RainScore}>}>}}};
type Binding={station_id:string;version:number;model_id:string|null;configuration_hash:string|null};
export default function ForecastRegistry(){
  const {user}=useAccount(),{selectedStationId}=useMonitoring();
  const [catalog,setCatalog]=useState<Catalog|null>(null),[binding,setBinding]=useState<Binding|null>(null),[error,setError]=useState('');
  const [selected,setSelected]=useState<Candidate|null>(null),[reason,setReason]=useState(''),[evidence,setEvidence]=useState(''),[decision,setDecision]=useState('approved');
  const [bindingReason,setBindingReason]=useState('');
  const [model,setModel]=useState(''),[busy,setBusy]=useState(false),[blocked,setBlocked]=useState(false);const generation=useRef(0);
  async function refresh(){const ticket=++generation.current;setSelected(null);setReason('');setEvidence('');setBlocked(false);setBinding(null);setModel('');setBindingReason('');setBusy(false);
    try{const [next,head]=await Promise.all([accountRequest<Catalog>('forecast-registry'),selectedStationId?accountRequest<Binding>(`forecast-deployments/${selectedStationId}`):Promise.resolve(null)]);if(ticket===generation.current){setCatalog(next);setBinding(head);setModel(head?.model_id??'');setError('');}}
    catch(error){if(ticket===generation.current)setError(error instanceof Error?error.message:'Registry unavailable');}}
  useEffect(()=>{void refresh();return()=>{++generation.current;};},[selectedStationId]);
  async function mutate(path:string,body:object){if(busy||blocked||error)return;const ticket=generation.current;setBusy(true);
    try{await accountRequest(path,'POST',body);if(ticket===generation.current)await refresh();}
    catch(error){if(ticket===generation.current){setError(error instanceof Error?error.message:'Review failed');setBlocked(true);setReason('');setEvidence('');setBindingReason('');}}
    finally{if(ticket===generation.current)setBusy(false);}}
  return <section className="design-panel p-4 flex flex-col gap-4" aria-label="Forecast registry and evaluation">
    <h3>Published water-depth forecast registry</h3><p>One reviewed station binding supplies both staff and residents. No operational model is approved by installing this code. Forecasts support advisory use; observations and official notices remain separate.</p>
    <button className="design-button" disabled={busy} onClick={()=>void refresh()}>Refresh registry and review manually</button>
    {error&&<p role="alert">{error}</p>}{blocked&&<p>Review changed. Refresh manually; no mutation was retried.</p>}
    {!catalog&&!error&&<p role="status">Checking the model registry; model state is unconfirmed.</p>}{catalog&&<p>Registry checked {catalog.checked_at??'at an unknown time'}; immutable evidence and captured review versions are shown.</p>}
    {catalog&&catalog.operational.length===0&&<p>No water-depth candidate is registered. Real site observations, licences, calibration and withheld events are still required.</p>}
    {catalog?.operational.map(item=><article key={item.id} className="border p-3 break-all"><h4>{item.card.station_id} · {item.state} · review {item.version}</h4><p>Model card {item.id}</p><p>Target: local sensor depth · cm · datum {item.card.datum}</p><p>Cutoff {item.card.training_cutoff} · source {item.card.source_class} · licence {item.card.data_license}</p><p>Features available at issue: {item.card.features}</p><p>{item.card.provenance}</p><p>{item.card.calibration_history}</p><p>Limitations: {item.card.limitations}</p><p>Use: {item.card.allowed_use} · fallback: {item.card.fallback}</p>
      <div className="overflow-x-auto"><table><caption>Withheld-event errors in cm</caption><thead><tr><th>Method</th><th>Horizon</th><th>Count</th><th>MAE</th><th>RMSE</th><th>Bias</th><th>Max error</th></tr></thead><tbody>{Object.entries(item.evaluation).flatMap(([method,scores])=>Object.entries(scores).map(([h,score])=><tr key={method+h}><td>{method}</td><td>{h} min</td><td>{score.count}</td><td>{score.mae_cm.toFixed(1)}</td><td>{score.rmse_cm.toFixed(1)}</td><td>{score.bias_cm.toFixed(1)}</td><td>{score.maximum_absolute_error_cm.toFixed(1)}</td></tr>))}</tbody></table></div>
      {user.role==='admin'&&<button className="design-button" disabled={busy||blocked||Boolean(error)} onClick={()=>{setSelected(structuredClone(item));setReason('');setEvidence('');}}>Review candidate {item.id.slice(0,8)}</button>}
      <DecisionEvaluation report={item.decision_evaluation}/>
    </article>)}
    {selected&&<form className="flex flex-col gap-2" onSubmit={event=>{event.preventDefault();if(reason.trim().length>=8&&/^[a-f0-9]{64}$/.test(evidence))void mutate(`forecast-registry/${selected.id}/review`,{expected_version:selected.version,decision,reason:reason.trim(),evidence_sha256:evidence});}}>
      <h4>Independent review · captured version {selected.version}</h4><p>Approval attests reviewed real-event evidence and permitted use. Registrants cannot approve their own candidate. Engineering gates do not replace domain review.</p>
      <label>Decision<select className="design-input" disabled={busy||blocked||Boolean(error)} value={decision} onChange={e=>setDecision(e.target.value)}><option value="approved">Approve reviewed adapter</option><option value="revoked">Revoke approval</option></select></label>
      <label>Reason<textarea className="design-input" minLength={8} maxLength={500} value={reason} onChange={e=>setReason(e.target.value)} disabled={busy||blocked||Boolean(error)}/></label>
      <label>External review evidence SHA-256<input className="design-input" maxLength={64} pattern="[a-f0-9]{64}" value={evidence} onChange={e=>setEvidence(e.target.value)} disabled={busy||blocked||Boolean(error)}/></label>
      <button className="design-button" disabled={busy||blocked||Boolean(error)||reason.trim().length<8||!/^[a-f0-9]{64}$/.test(evidence)}>Record independent decision</button>
    </form>}
    {binding&&<section><h4>{binding.station_id} · published binding {binding.version}</h4><p>Current model: {binding.model_id??'Unavailable — no deployed adapter'}</p>{user.role==='admin'&&<form className="flex flex-col gap-2" onSubmit={event=>{event.preventDefault();if(bindingReason.trim().length<8)return;const candidate=catalog?.operational.find(c=>c.id===model);void mutate(`forecast-deployments/${binding.station_id}`,{expected_version:binding.version,model_id:model||null,configuration_hash:candidate?.card.configuration_hash??null,reason:bindingReason.trim()});}}>
      <label>Reviewed station model<select className="design-input" value={model} disabled={busy||blocked||Boolean(error)} onChange={e=>setModel(e.target.value)}><option value="">Disable operational forecasts</option>{binding.model_id&&!catalog?.operational.some(c=>c.id===binding.model_id&&c.state==='approved')&&<option value={binding.model_id}>Current binding requires review · {binding.model_id}</option>}{catalog?.operational.filter(c=>c.state==='approved'&&c.card.station_id===binding.station_id).map(c=><option key={c.id} value={c.id}>{c.id}</option>)}</select></label>
      <label>Binding reason<textarea className="design-input" value={bindingReason} minLength={8} maxLength={500} onChange={e=>setBindingReason(e.target.value)} disabled={busy||blocked||Boolean(error)}/></label><button className="design-button" disabled={busy||blocked||Boolean(error)||bindingReason.trim().length<8}>Save reviewed station binding</button>
    </form>}</section>}
    <section><h3>Private rainfall experiment · configured artifact</h3><p>{catalog?.experimental.status==='available'?`${catalog.experimental.model_version} · ${catalog.experimental.source} · training cutoff ${catalog.experimental.training_cutoff}`:catalog?.experimental.reason??'Evaluation unavailable'}</p><p>{catalog?.experimental.notice}</p>
      {catalog?.experimental.evaluation&&<><table><caption>Archived rainfall errors in mm; these are not field water-depth errors</caption><thead><tr><th>Method</th><th>Scope</th><th>MAE mm</th><th>RMSE mm</th><th>Count</th></tr></thead><tbody>{Object.entries(catalog.experimental.evaluation.test).flatMap(([name,value])=>Object.entries({pooled:{overall:value.overall},...value.by_horizon}).map(([h,row])=><tr key={name+h}><td>{name}</td><td>{h}</td><td>{row.overall.mae_mm?.toFixed(2)??'—'}</td><td>{row.overall.rmse_mm?.toFixed(2)??'—'}</td><td>{row.overall.count}</td></tr>))}</tbody></table>
      <p>Compare every horizon with persistence. {(()=>{const e=catalog.experimental.evaluation!.test,ml=e.random_forest?.by_horizon?.['1h']?.overall.mae_mm,base=e.persistence?.by_horizon?.['1h']?.overall.mae_mm;return ml!=null&&base!=null?(base<ml?`First-hour persistence has lower MAE (${base.toFixed(2)} mm) than the rainfall model (${ml.toFixed(2)} mm).`:'The configured artifact does not show a first-hour persistence advantage; inspect the horizon scores.'):'First-hour comparison unavailable for this artifact.';})()} Pooled retrospective rainfall scores do not establish flood-warning quality.</p></>}
      <p className="break-all">Artifact {catalog?.experimental.artifact_sha256??'unknown'} · evaluation {catalog?.experimental.evaluation_sha256??'unknown'}</p>
    </section>
  </section>;
}
