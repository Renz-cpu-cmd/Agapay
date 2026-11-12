export type WorkflowMetric={count:number;failures:number;total_seconds:number;maximum_seconds:number;p95_seconds_upper_bound?:number|null;p99_seconds_upper_bound?:number|null};
export type OperationalComponent={name:string;state:string;required:boolean;code:string|null;message:string;pending?:number;processing?:number;uncertain?:number;failed?:number;stalled?:number;oldest_pending_seconds?:number;oldest_processing_seconds?:number|null;queue_budget_seconds?:number;provider_mode?:string};
export type OperationalDiagnostics={checked_at:string;status:string;ready:boolean;components:OperationalComponent[];alerts:{code:string;severity:string;message:string}[];
  metrics_window_minutes?:number;metrics?:Record<string,WorkflowMetric>;
  workers?:{role:string;state:string;observed_at:string;last_success_at:string|null;age_seconds:number;fresh:boolean}[];
  ingress?:{stations_checked:number;stale_or_missing_eligible_receipt_count:number;receipt_budget_seconds:number;bounded:boolean};
  budgets?:{station_limit:number;water_attempts_per_station_minute:number;rain_attempts_per_station_minute:number;queue_age_seconds:number};
  external_quotas?:{service:string;state:string;reason:string}[]};
export function evidenceIsCurrent(checkedAt:string|undefined,now:number){
  const age=checkedAt?now-Date.parse(checkedAt):NaN;
  return Number.isFinite(age)&&age>=0&&age<=45000;
}
export function latencyBound(value:number|null|undefined,count:number){
  if(count===0)return 'No observations';
  return value==null?'Beyond largest bucket / unavailable':`≤${value.toFixed(3)} s bucket upper bound`;
}
export function agedWorkerState(worker:NonNullable<OperationalDiagnostics['workers']>[number],checkedAt:string,now:number,known:boolean){
  const elapsed=Math.max(0,(now-Date.parse(checkedAt))/1000);
  if(!known||!worker.fresh||!Number.isFinite(elapsed)||worker.age_seconds+elapsed>45)return 'unconfirmed / stale';
  const progress=worker.last_success_at?now-Date.parse(worker.last_success_at):NaN;
  if(worker.state==='healthy'&&(!Number.isFinite(progress)||progress<0||progress>45000))return 'no recent successful progress';
  return worker.state;
}
