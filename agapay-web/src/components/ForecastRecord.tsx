"use client";
import {useEffect,useState} from 'react';
import {accountRequest} from '@/lib/accounts';
import {forecastDepth,forecastInterval,parsePublishedPrediction,type Prediction} from '@/lib/predictions';
export default function ForecastRecord({id}:{id:string}){
  const [data,setData]=useState<Prediction|null>(null),[current,setCurrent]=useState(false),[error,setError]=useState('');
  useEffect(()=>{const controller=new AbortController();setData(null);void accountRequest<{product:unknown;current:boolean;read_at:string}>(`forecasts/${id}`,'GET',undefined,controller.signal).then(result=>{
    if(controller.signal.aborted)return;const product=parsePublishedPrediction(result.product);if(product.forecast_id!==id)throw Error('Forecast identity mismatch');
    setData(product);setCurrent(result.current===true&&Boolean(product.valid_until)&&Date.parse(product.valid_until!)>Date.parse(result.read_at));
  }).catch(error=>{if(!controller.signal.aborted)setError(error instanceof Error?error.message:'Forecast record unavailable');});return()=>controller.abort();},[id]);
  return <section className="design-panel p-4 flex flex-col gap-3"><h2>Published forecast record</h2><p>This immutable record is separate from current measurements, alerts and authority-issued instructions.</p>{error&&<p role="alert">{error}</p>}{data&&<>
    <p>{current?'Within its original validity at read time':'Historical, expired or withdrawn — do not use as a current forecast'}</p><p className="break-all">Forecast {data.forecast_id} · {data.station_id}</p><p>Generated {data.generated_at} · expires {data.valid_until} · input cutoff {data.data_cutoff}</p><p>Target local sensor depth · cm · datum {data.reference_datum}</p><p className="break-all">Model {data.model_card_id} · binding {data.deployment_version} · configuration {data.configuration_hash}</p><p>Source {data.ingress_identity} · registry {data.registry_version}</p>
    <table><caption>Original published values, never extended by opening this record</caption><thead><tr><th>Horizon</th><th>Target UTC</th><th>Approximate depth cm</th><th>Event-calibrated interval</th></tr></thead><tbody>{data.forecasts.map(point=><tr key={point.horizon_minutes}><td>+{point.horizon_minutes} min</td><td>{point.target_at}</td><td>{forecastDepth(point.water_depth_cm,data.uncertainty?.display_resolution_cm)}</td><td>{forecastInterval(point.lower_depth_cm,point.upper_depth_cm)}</td></tr>)}</tbody></table>
  </>}</section>;
}
