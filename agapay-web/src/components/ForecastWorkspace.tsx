"use client";
import {useEffect,useState} from 'react';
import Link from 'next/link';
import {useMonitoring} from '@/context/MonitoringContext';
import {useAlertResource} from '@/hooks/useAlertResource';
import {useEvidenceClock} from '@/hooks/useEvidenceClock';
import {accountRequest} from '@/lib/accounts';
import {alertTime} from '@/lib/alerts';
import {forecastDepth,forecastInterval,type Prediction} from '@/lib/predictions';
import {publicationState,publishedEvidence,type ForecastWorkspaceData,type ForecastEnvelope} from '@/lib/forecast-workspace';
import DecisionEvaluation from './DecisionEvaluation';
import MLWorkspaceHeader from './MLWorkspaceHeader';
import type {Candidate} from './ForecastRegistry';

function DeployedEvaluation({data}:{data:ForecastWorkspaceData}){
  const model=data.model,head=data.deployment;
  const [evidence,setEvidence]=useState<Candidate|null>(null),[error,setError]=useState(''),[revision,setRevision]=useState(0);
  useEffect(()=>{
    const controller=new AbortController();setEvidence(null);setError('');
    if(model)void accountRequest<Candidate>(`forecast-registry/${model.id}/evidence`,'GET',undefined,AbortSignal.any([controller.signal,AbortSignal.timeout(10000)]))
      .then(value=>{if(controller.signal.aborted)return;if(value.id!==model.id||value.card.station_id!==data.station_id||value.version!==model.version||value.card.configuration_hash!==head.configuration_hash)throw Error('Evaluation, review or station configuration changed. Refresh and review the binding.');setEvidence(value);})
      .catch(reason=>{if(!controller.signal.aborted)setError(reason instanceof Error?reason.message:'Deployed evidence unavailable');});
    return()=>controller.abort();
  },[model?.id,model?.version,data.station_id,head.configuration_hash,revision]);
  return <section className="design-panel p-4"><div className="design-toolbar"><h2>Deployed model evidence</h2><button className="design-button" onClick={()=>setRevision(n=>n+1)}>Refresh deployed evaluation</button></div>
    <p className="subtle-note">This section follows the current station binding. Compare its model ID and configuration with any historical product selected above; it does not retroactively approve an earlier release.</p>
    {!model&&<p>No operational adapter is deployed. Experimental rainfall scores are not a substitute for site water-depth evidence.</p>}
    {error&&<p role="alert">{error}</p>}{model&&!evidence&&!error&&<p role="status">Checking evaluation for the exact deployed model…</p>}
    {evidence&&<><p className="hash-value">Model {evidence.id} · {evidence.state} · review {evidence.version}</p><dl className="evidence-grid">
      <div><dt>Target and datum</dt><dd>Local sensor depth, cm · {evidence.card.datum}</dd></div><div><dt>Training cutoff / source</dt><dd>{alertTime(evidence.card.training_cutoff)} · {evidence.card.source_class}</dd></div>
      <div><dt>Inference features</dt><dd>{evidence.card.features}</dd></div><div><dt>Data licence and provenance</dt><dd>{evidence.card.data_license} · {evidence.card.provenance}</dd></div>
      <div><dt>Calibration history</dt><dd>{evidence.card.calibration_history}</dd></div><div><dt>Allowed use / fallback</dt><dd>{evidence.card.allowed_use} · {evidence.card.fallback}</dd></div></dl>
      <p><strong>Limits:</strong> {evidence.card.limitations}</p>
      <div className="design-table-wrap"><table className="design-table"><caption>Withheld-event depth errors in cm; candidate and reference baselines</caption><thead><tr><th>Method</th><th>Horizon min</th><th>Samples</th><th>MAE cm</th><th>RMSE cm</th><th>Bias cm</th><th>Maximum error cm</th></tr></thead><tbody>{Object.entries(evidence.evaluation).flatMap(([method,horizons])=>Object.entries(horizons).map(([h,score])=><tr key={method+h}><td>{method}</td><td>{h}</td><td>{score.count}</td><td>{score.mae_cm.toFixed(1)}</td><td>{score.rmse_cm.toFixed(1)}</td><td>{score.bias_cm.toFixed(1)}</td><td>{score.maximum_absolute_error_cm.toFixed(1)}</td></tr>))}</tbody></table></div>
      <DecisionEvaluation report={evidence.decision_evaluation}/>
    </>}
  </section>;
}

function ProductEvidence({data,envelope,now}:{data:ForecastWorkspaceData;envelope:ForecastEnvelope;now:number}){
  let product:Prediction;
  try{product=publishedEvidence(envelope,data.station_id);}catch{return <p role="alert">Published evidence could not be validated for this station. No forecast values are shown.</p>;}
  const state=publicationState(data,product,envelope,now),u=product.uncertainty!;
  return <article className="published-evidence">
    <p className="operational-state" data-state={state==='current'?'published':state==='historical'?'stale':'unknown'}>{state==='current'?'Current reviewed advisory product':state==='historical'?'Historical, expired or withdrawn product':'Current publication unconfirmed; retained product evidence'}</p>
    <p className="subtle-note">Advisory use only. This product does not issue an evacuation order or replace current observations.</p>
    <dl className="evidence-grid"><div><dt>Forecast reference</dt><dd>{product.forecast_id}</dd></div><div><dt>Published binding / model</dt><dd>Version {product.deployment_version}<p className="hash-value">{product.model_card_id}</p></dd></div>
      <div><dt>Generated / expires</dt><dd>{alertTime(product.generated_at)} / {alertTime(product.valid_until)}</dd></div><div><dt>Input coverage and cutoff</dt><dd>{product.valid_sample_count} valid / {product.sample_count} observations<p>{alertTime(product.input_window_start)} to {alertTime(product.data_cutoff??null)}</p></dd></div>
      <div><dt>Target / source identity</dt><dd>Local depth, cm · datum {product.reference_datum}<p>{product.ingress_identity} · registry {product.registry_version} · {product.measurement_source}</p></dd></div>
      <div><dt>Published configuration hash</dt><dd className="hash-value">{product.configuration_hash}</dd></div>
      <div><dt>Event uncertainty evidence</dt><dd>{u.calibration_events} calibration / {u.test_events} withheld events · nominal {(u.nominal_coverage*100).toFixed(0)}% · observed {(u.withheld_event_coverage*100).toFixed(0)}%</dd></div>
      <div><dt>Uncertainty policy / display resolution</dt><dd className="hash-value">{u.policy_sha256}<p>Approximate values at {u.display_resolution_cm} cm resolution</p></dd></div></dl>
    <p>{u.notice} Coverage is an event evaluation measure, not the probability that an area is safe.</p>
    <div className="design-table-wrap"><table className="design-table"><caption>Original published horizons and event-calibrated intervals; no interpolation across missing evidence</caption><thead><tr><th>Horizon</th><th>Target (PHT)</th><th>Approximate depth cm</th><th>Calibrated interval</th></tr></thead><tbody>{product.forecasts.map(point=><tr key={point.horizon_minutes}><td>+{point.horizon_minutes} min</td><td>{alertTime(point.target_at)}</td><td>{forecastDepth(point.water_depth_cm,u.display_resolution_cm)}</td><td>{forecastInterval(point.lower_depth_cm,point.upper_depth_cm)}</td></tr>)}</tbody></table></div>
    <Link className="design-button" href={`/forecasts/${product.forecast_id}`}>Open immutable forecast record</Link>
  </article>;
}

function StationForecastEvidence({stationId}:{stationId:string}){
  const [offset,setOffset]=useState(0),[revision,setRevision]=useState(0),[chosen,setChosen]=useState('');
  const resource=useAlertResource<ForecastWorkspaceData>(`forecast-workspaces/${stationId}?limit=5&offset=${offset}&refresh=${revision}`);
  const data=resource.data?.station_id===stationId?resource.data:null,now=useEvidenceClock();
  const selected=data?.products.find(row=>(row.product as Prediction).forecast_id===chosen)??data?.products[0];
  return <><section className="design-panel p-4"><div className="design-toolbar"><h2>Published version and model state</h2><button className="design-button" onClick={()=>setRevision(n=>n+1)}>Refresh publication evidence</button></div>
    {resource.loading&&<p role="status">Checking published products…</p>}{(resource.error||resource.data&&!data)&&<p role="alert">Forecast evidence unavailable. Publication, model state and coverage cannot be confirmed.</p>}
    {data&&<><p>Publication: {data.publication_status.replaceAll('_',' ')} · {data.publication_reason}</p><dl className="evidence-grid"><div><dt>Selected station / deployed binding</dt><dd>{data.station_id} · version {data.deployment.version}</dd></div><div><dt>Model review state</dt><dd>{data.model?`${data.model.state} · current review ${data.model.version} · bound review ${data.deployment.model_review_version}`:'No deployed water-depth model'}</dd></div><div><dt>Current model review evidence</dt><dd className="hash-value">{data.model?.evidence_sha256??'Not recorded'}</dd></div><div><dt>Publication checked</dt><dd>{alertTime(data.checked_at)} · {now<=0||now-Date.parse(data.checked_at)<0||now-Date.parse(data.checked_at)>45000?'Current state unconfirmed; refresh required':'Original product expiry still applies'}</dd></div></dl>
      <label className="forecast-product-picker">Published product in this page<select aria-label="Published product in this page" className="design-input" value={selected?(selected.product as Prediction).forecast_id??'':''} onChange={e=>setChosen(e.target.value)}>{data.products.map(row=>{const p=row.product as Prediction;return <option key={p.forecast_id} value={p.forecast_id??''}>{p.forecast_id} · generated {alertTime(p.generated_at)}</option>;})}</select></label>
      {selected?<ProductEvidence data={data} envelope={selected} now={now}/>:<p>No product has been published for this station. Forecast values and uncertainty remain unavailable.</p>}
      <div className="design-controls"><button className="design-button" disabled={!offset} onClick={()=>{setOffset(Math.max(0,offset-5));setChosen('');}}>Newer products</button><span>{data.total} immutable product(s); up to five shown</span><button className="design-button" disabled={!data.has_more} onClick={()=>{setOffset(offset+5);setChosen('');}}>Older products</button></div>
    </>}
  </section>{data&&<DeployedEvaluation data={data}/>}</>;
}

export default function ForecastWorkspace(){
  const {stations,selectedStationId,selectStation,loading,error}=useMonitoring();
  const station=stations.find(s=>s.id===selectedStationId)??stations[0];
  useEffect(()=>{if(!selectedStationId&&stations[0])selectStation(stations[0].id);},[selectedStationId,stations,selectStation]);
  return <div className="ml-workspace staff-decisions forecast-workspace"><MLWorkspaceHeader page="published"/><div className="design-toolbar">{station&&<label>Forecast station<select aria-label="Forecast station" className="design-input" value={station.id} onChange={e=>selectStation(e.target.value)}>{stations.map(s=><option key={s.id} value={s.id}>{s.name} · {s.id}</option>)}</select></label>}</div>
    {error&&<p role="status">Monitoring registry is unavailable. Retained station names do not confirm current measurements.</p>}
    {station?<StationForecastEvidence key={station.id} stationId={station.id}/>:<section className="design-panel p-4"><h2>{loading?'Checking station registry…':'No station context available'}</h2><p>No forecast or trained model is inferred from an empty station list.</p></section>}

  </div>;
}
