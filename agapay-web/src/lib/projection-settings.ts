// Persist setup choices only. Forecast values are always recomputed from the API.
export type Basin = {
  contributing_area_m2:number; basin_surface_area_m2:number; runoff_coefficient:number;
  outflow_m3_per_hour:number; maximum_depth_cm:number;
};
export type ProjectionConfiguration = {
  mode:string; depthSource:string; rainSource:string; initial:string; context:string;
  basin:Basin; basis:Record<string,string>; confirmed:boolean;
};
export type ProjectionSetup = {config:ProjectionConfiguration;active:boolean};
export const projectionStorageKey = (accountId:number) => `agapay-projection-setup:v1:${accountId}`;
const basisNames = ["assumed","estimated","measured"];
const basinKeys = ["contributing_area_m2","basin_surface_area_m2","runoff_coefficient","outflow_m3_per_hour","maximum_depth_cm"] as const;
const object = (value:unknown):value is Record<string,unknown> => Boolean(value) && typeof value==="object" && !Array.isArray(value);

export function decodeProjectionSetups(raw:string|null):Record<string,ProjectionSetup> {
  const setups:Record<string,ProjectionSetup> = {};
  try {
    const document:unknown=JSON.parse(raw??"null");
    if(!object(document)||document.version!==1||!object(document.stations))return setups;
    for(const [station,value] of Object.entries(document.stations).slice(0,50)) {
      if(!station || station.length>120 || ["__proto__","constructor","prototype"].includes(station) || !object(value) || !object(value.config))continue;
      const c=value.config;
      if(!["historical_context","live"].includes(String(c.mode)) || !["manual","sensor"].includes(String(c.depthSource)) ||
         !["physical_rain_gauge","simulated_rain_gauge"].includes(String(c.rainSource)) ||
         typeof c.initial!=="string" || !c.initial.trim() || !Number.isFinite(Number(c.initial)) || Number(c.initial)<0 || Number(c.initial)>1000 ||
         typeof c.context!=="string" || !/^2025-\d{2}-\d{2}T\d{2}:00$/.test(c.context) || !Number.isFinite(Date.parse(c.context+":00Z")) ||
         typeof c.confirmed!=="boolean" || !object(c.basin) || !object(c.basis))continue;
      if(c.mode==="historical_context" && c.depthSource!=="manual")continue;
      const basin=c.basin,basis=c.basis;
      if(basinKeys.some(key=>typeof basin[key]!=="number" || !Number.isFinite(basin[key]) || !basisNames.includes(String(basis[key]))))continue;
      if(Number(basin.contributing_area_m2)<=0 || Number(basin.basin_surface_area_m2)<=0 || Number(basin.maximum_depth_cm)<=0 ||
         Number(basin.runoff_coefficient)<0 || Number(basin.runoff_coefficient)>1 || Number(basin.outflow_m3_per_hour)<0)continue;
      const config:ProjectionConfiguration={mode:String(c.mode),depthSource:String(c.depthSource),rainSource:String(c.rainSource),
        initial:c.initial,context:c.context,confirmed:c.confirmed,
        basin:{contributing_area_m2:Number(basin.contributing_area_m2),basin_surface_area_m2:Number(basin.basin_surface_area_m2),
          runoff_coefficient:Number(basin.runoff_coefficient),outflow_m3_per_hour:Number(basin.outflow_m3_per_hour),maximum_depth_cm:Number(basin.maximum_depth_cm)},
        basis:Object.fromEntries(basinKeys.map(key=>[key,String(basis[key])]))};
      setups[station]={config,active:value.active===true && config.confirmed};
    }
  } catch { /* Corrupt or unavailable storage never enables a projection. */ }
  return setups;
}

export const encodeProjectionSetups = (setups:Record<string,ProjectionSetup>) => JSON.stringify({version:1,stations:setups});

// The previously verified local cardboard demo. Never replace a saved choice or
// auto-configure an unknown station, simulator, remote deployment or stale input.
export function withAutomaticDemoSetup(setups:Record<string,ProjectionSetup>, station:{
  station_id:string;source:string;is_online:boolean;sensor_quality:string|null;current_depth_cm:number|null;
  source_class:string;source_trusted:boolean;depth_source_trusted:boolean;depth_fresh:boolean;heartbeat_fresh:boolean;stream:string;
}|undefined, localDemo:boolean):Record<string,ProjectionSetup> {
  if(!localDemo || !station || station.station_id!=="STATION_001" || Object.hasOwn(setups,station.station_id) ||
     station.source!=="device" || !station.is_online || station.sensor_quality!=="valid" ||
     station.source_class!=="physical_device" || !station.source_trusted || !station.depth_source_trusted ||
     !station.depth_fresh || !station.heartbeat_fresh || station.stream!=="operational" ||
     station.current_depth_cm===null || !Number.isFinite(station.current_depth_cm))return setups;
  const basin:Basin={contributing_area_m2:2,basin_surface_area_m2:.1,runoff_coefficient:.8,outflow_m3_per_hour:0,maximum_depth_cm:100};
  return {...setups,[station.station_id]:{active:true,config:{
    mode:"live",depthSource:"sensor",rainSource:"physical_rain_gauge",initial:"20",
    context:"2025-07-01T12:00",basin,basis:Object.fromEntries(basinKeys.map(key=>[key,"assumed"])),confirmed:true,
  }}};
}
