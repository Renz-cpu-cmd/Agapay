import type { Station } from "../data/mockData";

export type Ownership = {revision:number;owner_id:number|null;owner_name:string|null;changed_at:string|null};
export type CommandEpisode = {id:number;station_id:string;station_name:string;severity:"ADVISORY"|"WARNING"|"EVACUATE";
  triggered_at:string;last_transition_at:string;latest_telemetry_id:number;latest_depth_cm:number;
  ownership:Ownership;areas:{id:string;name:string}[];source:"recorded_physical"|"unverified"};
export type CommandQueue = {items:CommandEpisode[];total:number;has_more:boolean;checked_at:string;scope:"operational"|"unverified";counts:{operational:number;unverified:number}};
export type SampleEvidence = {id:number;measured_at:string|null;received_at:string;quality:string;disposition:string;
  source_id:string|null;registry_version:number|null;transport:string|null;source_class:string};
export type StationWorkspace = {station_id:string;checked_at:string;identity:null|{device_id:string;version:number;state:string;
  coordinates_verified:boolean;datum:string;calibration_note:string;commissioned_at:string|null};
  latest_sample:SampleEvidence|null;last_valid:SampleEvidence|null;latest_received:SampleEvidence|null;
  events:{id:number;action:string;actor:string;reason:string;created_at:string}[];total:number;has_more:boolean};

export function elapsedLabel(value:string|null|undefined, now=Date.now()) {
  const ms=value?now-Date.parse(value):NaN;
  if(!Number.isFinite(ms)||ms<0)return "Time unconfirmed";
  const seconds=Math.floor(ms/1000);
  if(seconds<60)return `${seconds}s elapsed`;
  if(seconds<3600)return `${Math.floor(seconds/60)}m elapsed`;
  if(seconds<86400)return `${Math.floor(seconds/3600)}h ${Math.floor(seconds%3600/60)}m elapsed`;
  return `${Math.floor(seconds/86400)}d ${Math.floor(seconds%86400/3600)}h elapsed`;
}
export function readIsCurrent(checkedAt:string|undefined, now=Date.now()) {
  const age=checkedAt?now-Date.parse(checkedAt):NaN;
  return Number.isFinite(age)&&age>=0&&age<=15000;
}
export function reviewAction(station:Station|undefined) {
  if(!station)return "Open the station workspace; current measurement evidence is unavailable.";
  if(station.configuration?.status!=="matched")return "Review device/server configuration before relying on this depth.";
  if(!station.depthFresh)return "Check the last-valid time and sensor fault; keep unresolved hazards under review.";
  if(!station.sourceTrusted||!station.depthSourceTrusted)return "Verify the recorded source identity and commissioning record.";
  return "Review measured trend and affected-area bindings; consult the issuing authority for public actions.";
}
// A gap is a missing observation, never a connecting estimate. No inferred cadence
// is used: the monitoring expiry is the maximum drawable interval.
export function measuredSeries(history:Station["waterHistory"], maximumGapSeconds:number):{at:number;level:number|null;gapStart?:number;gapEnd?:number}[] {
  const rows=history.filter(row=>row.measuredAt&&Number.isFinite(Date.parse(row.measuredAt)))
    .map(row=>({at:Date.parse(row.measuredAt!),level:row.level})).sort((a,b)=>a.at-b.at);
  return rows.flatMap((row,i)=>i&&row.at-rows[i-1].at>maximumGapSeconds*1000
    ? [{at:rows[i-1].at+1,level:null,gapStart:rows[i-1].at,gapEnd:row.at},row]:[row]);
}
export function stationFaults(station:Station) {
  if(station.administrativeStatus!=="active")return [`Administration: ${station.lifecycle?.state??station.administrativeStatus??"unknown"}`];
  const channels=station.channelHealth;
  if(!channels)return ["Independent health unavailable"];
  return (["device_heartbeat","water_sensor","rain_counter","broker_ingestion"] as const)
    .filter(key=>channels[key].state!=="healthy").map(key=>`${key.replaceAll("_"," ")}: ${channels[key].state}`);
}
