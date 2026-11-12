import {parsePublishedPrediction,type Prediction} from './predictions';
export type ForecastEnvelope={product:unknown;read_at:string;current:boolean};
export type ForecastWorkspaceData={station_id:string;checked_at:string;deployment:{station_id:string;version:number;model_id:string|null;configuration_hash:string|null;model_review_version:number|null};
  model:{id:string;state:string;version:number;evidence_sha256:string|null}|null;publication_status:string;publication_reason:string;current_forecast_id:string|null;
  products:ForecastEnvelope[];total:number;has_more:boolean};
export function publishedEvidence(envelope:ForecastEnvelope,stationId:string):Prediction {
  const product=parsePublishedPrediction(envelope.product);
  if(product.station_id!==stationId||product.status!=='available'||!product.forecast_id)throw Error('Published evidence does not match this station.');
  return product;
}
export function publicationState(data:ForecastWorkspaceData,product:Prediction,envelope:ForecastEnvelope,now:number){
  const age=now-Date.parse(data.checked_at);
  if(!Number.isFinite(age)||age<0||age>45000)return 'unconfirmed';
  return envelope.current&&data.current_forecast_id===product.forecast_id&&data.publication_status==='available'
    &&data.deployment.model_id===product.model_card_id&&data.deployment.version===product.deployment_version
    &&data.model?.state==='approved'&&data.model.version===data.deployment.model_review_version
    &&Boolean(product.valid_until)&&Date.parse(product.valid_until!)>now?'current':'historical';
}
