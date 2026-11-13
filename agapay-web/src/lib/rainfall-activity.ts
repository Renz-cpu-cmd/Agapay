export type RainHour = {timestamp_utc:string;rainfall_mm:number|null;interval_seconds:number;valid:boolean};
export type RainSnapshot = {
  station_id:string;data_source:string;connected:boolean;checked_at:string;status:string;
  last_received_at?:string;current_hour_start?:string;incomplete_hour_mm?:number;
  completed_hours:RainHour[];
  source_trusted?:boolean;
  calibration_version?:string;current_hour_product?:{interval_start:string;interval_end:string;coverage:string};
};
const hour=3600000;

export function selectRainActivity(snapshot:RainSnapshot|null, station:string, source:string, now:number, unavailable:boolean,
                                  archived:RainHour[]=[]) {
  const received=Date.parse(snapshot?.last_received_at??"");
  const fresh=!unavailable && snapshot?.source_trusted!==false && snapshot?.station_id===station && snapshot.data_source===source && snapshot.connected
    && Number.isFinite(received) && now>=received && now-received<=30000;
  const currentStart=Math.floor(now/hour)*hour;
  const amount=snapshot?.incomplete_hour_mm;
  const current=fresh && Date.parse(snapshot?.current_hour_start??"")===currentStart && typeof amount==="number" && Number.isFinite(amount) && amount>=0 ? amount:null;
  // Unknown intervals stay null; a missing observation must never become dry weather.
  const rows=fresh?snapshot!.completed_hours:archived;
  const chart=rows.filter(row=>Number.isFinite(Date.parse(row.timestamp_utc))).slice(-24).map(row=>({
    at:row.timestamp_utc,
    amount:row.valid && row.interval_seconds===3600 && typeof row.rainfall_mm==="number" && Number.isFinite(row.rainfall_mm) && row.rainfall_mm>=0 ? row.rainfall_mm:null,
    partial:false,
  }));
  if(fresh && current!==null)chart.push({at:new Date(currentStart+hour).toISOString(),amount:current,partial:true});
  return {fresh:Boolean(fresh),current,chart,chartSource:fresh?"gauge":chart.some(row=>row.amount!==null)?"archive":"none",received:fresh?received:null} as const;
}
