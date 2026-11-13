export interface HistoryBucket {
  bucket_start:string; bucket_end:string; mean_depth_cm:number|null; minimum_depth_cm:number|null; maximum_depth_cm:number|null;
  sample_count:number; valid_count:number; invalid_count:number; review_count:number; unverified_count:number;
  first_measured_at:string|null; last_measured_at:string|null; quality:string; sources:Record<string,number>; source_details:Record<string,number>;
}
export interface HistoryStation {
  station_id:string;station_name:string;unit:"cm";minimum_depth_cm:number|null;maximum_depth_cm:number|null;mean_depth_cm:number|null;
  sample_count:number;valid_count:number;invalid_count:number;review_count:number;unverified_count:number;
  covered_buckets:number;expected_buckets:number;sources:Record<string,number>;source_details:Record<string,number>;buckets:HistoryBucket[];
}
export interface HistoryReport {
  checked_at:string;scope:{start_at:string;end_at:string;start_local:string;end_local:string;timezone:"UTC"|"Asia/Manila";
    station_ids:string[];event_id:number|null;event_status:string|null;event_started_at:string|null;event_resolved_at:string|null;
    bucket_seconds:number;boundary:string;timestamp_basis:string;aggregation:string;coverage_basis:string;rainfall_scope:string;
    rows_scanned:number;unsynchronized_rows_excluded:number};stations:HistoryStation[];
}
export function historySeries(report:HistoryReport) {
  const byTime=new Map<string,Record<string,unknown>>();
  for(const station of report.stations)for(const bucket of station.buckets){
    const point=byTime.get(bucket.bucket_start)??{at:Date.parse(bucket.bucket_start),time:bucket.bucket_start};
    point[station.station_id]=bucket.mean_depth_cm;byTime.set(bucket.bucket_start,point);
  }
  return [...byTime.values()].sort((a,b)=>Number(a.at)-Number(b.at));
}
export function reportCsv(report:HistoryReport):string {
  const rows:unknown[][]=[['AGAPAY measured water-depth report'],['As of',report.checked_at]];
  for(const [key,value]of Object.entries(report.scope))rows.push([key,Array.isArray(value)?value.join(';'):value??'—']);
  rows.push([],['station_id','station_name','unit','minimum_depth_cm','maximum_depth_cm','mean_depth_cm','valid_samples','received_samples','covered_buckets','expected_buckets','source_classes','authenticated_source_details']);
  for(const station of report.stations)rows.push([station.station_id,station.station_name,station.unit,station.minimum_depth_cm??'—',station.maximum_depth_cm??'—',station.mean_depth_cm??'—',station.valid_count,station.sample_count,station.covered_buckets,station.expected_buckets,JSON.stringify(station.sources),JSON.stringify(station.source_details)]);
  rows.push([],['station_id','bucket_start_utc','bucket_end_utc','unit','mean_depth_cm','minimum_depth_cm','maximum_depth_cm','quality','valid_count','sample_count','invalid_count','review_count','unverified_count','first_measured_at','last_measured_at','source_classes','authenticated_source_details']);
  for(const station of report.stations)for(const bucket of station.buckets)rows.push([station.station_id,bucket.bucket_start,bucket.bucket_end,station.unit,bucket.mean_depth_cm??'—',bucket.minimum_depth_cm??'—',bucket.maximum_depth_cm??'—',bucket.quality,bucket.valid_count,bucket.sample_count,bucket.invalid_count,bucket.review_count,bucket.unverified_count,bucket.first_measured_at??'—',bucket.last_measured_at??'—',JSON.stringify(bucket.sources),JSON.stringify(bucket.source_details)]);
  const cell=(value:unknown)=>{
    const text=String(value);
    // Quoting alone does not stop spreadsheet formulas in names or metadata.
    const literal=typeof value==='string'&&/^\s*[=+\-@\t\r\n]/.test(text)?`'${text}`:text;
    return `"${literal.replaceAll('"','""')}"`;
  };
  return '\uFEFF'+rows.map(row=>row.map(cell).join(',')).join('\r\n');
}
export function localInputToUtc(value:string,timeZone:"UTC"|"Asia/Manila") {
  return new Date(`${value}${timeZone==="UTC"?"Z":"+08:00"}`).toISOString();
}
