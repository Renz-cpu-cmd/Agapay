"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { visiblePoll } from "@/lib/visible-poll";
import { accountRequest } from "@/lib/accounts";
import { useAccount } from "@/context/AccountContext";
import { useMonitoring } from "@/context/MonitoringContext";
import { monitoringStationForDisplay } from "@/lib/monitoring";
import { decodeProjectionSetups,encodeProjectionSetups,projectionStorageKey,withAutomaticDemoSetup,type Basin,type ProjectionConfiguration,type ProjectionSetup } from "@/lib/projection-settings";
export type { Basin } from "@/lib/projection-settings";

export type Projection = {
  station_id: string; status: "available" | "unavailable"; reason: string; mode: string;
  checked_at: string; valid_until?: string; initialization_at?: string; initial_source?: string;
  initial_depth_cm?: number; rainfall_source?: string; rainfall_context_at?: string; model_version?: string;
  observed_rainfall_since_initialization_mm?: number; adjusted?: { depth_cm: number };
  rainfall_history?: { timestamp_utc: string; rainfall_mm: number; interval_seconds: number; valid: boolean }[];
  points: { horizon_minutes: number; depth_cm: number; target_at: string }[];
  rain_snapshot?: { data_source: string; boot_session_tip_count: number; session_rainfall_mm: number;
    incomplete_hour_mm: number; latest_increment_mm: number; last_tip_at: string | null; ml_ready: boolean;
    latest_tip_event_id: number; unallocated_recovered_mm: number; mm_per_tip: number } | null;
};
export const defaultBasin: Basin = { contributing_area_m2: 2, basin_surface_area_m2: .1, runoff_coefficient: .8, outflow_m3_per_hour: 0, maximum_depth_cm: 100 };
type Configuration = ProjectionConfiguration;
const defaults: Configuration = {
  mode: "historical_context", depthSource: "manual", rainSource: "physical_rain_gauge", initial: "20",
  context: "2025-07-01T12:00", basin: defaultBasin,
  basis: Object.fromEntries(Object.keys(defaultBasin).map(key=>[key,"assumed"])), confirmed: false,
};
type Result = { data: Projection | null; error: string; newTip: boolean };
const emptyResult: Result = {data:null,error:"",newTip:false};
type Setup = ProjectionSetup;
type State = {
  setups: Record<string,Setup>; results: Record<string,Result>; clock: number;
  configure: (station: string, patch: Partial<Configuration>) => void;
  start: (station: string) => void; stop: (station: string) => void;
  subscribe:(station:string)=>()=>void;
};
const Context = createContext<State | null>(null);

function ProjectionFeed({stationId, config, report}: {stationId:string; config:Configuration; report:(station:string,result:Result)=>void}) {
  useEffect(()=>{
    let stopped=false, anchor: string | undefined;
    let lastTip: number | undefined;
    async function poll(signal:AbortSignal) {
      try {
        const next=await accountRequest<Projection>(`hybrid-projections/${encodeURIComponent(stationId)}`, "POST", {
          mode:config.mode, depth_source:config.depthSource, manual_depth_cm:Number(config.initial), initialization_at:anchor,
          context_at:config.context+":00Z", rain_source:config.rainSource, controlled_basin_confirmed:config.confirmed,
          basin:{...config.basin,parameter_basis:config.basis},
        },AbortSignal.any([signal,AbortSignal.timeout(5000)]));
        if(stopped || signal.aborted)return;
        if(next.station_id!==stationId || !["available","unavailable"].includes(next.status))throw Error("Projection station or status did not match.");
        let newTip=false;
        if(next.status==="available") {
          if(next.points.length!==3 || next.points.some((p,i)=>p.horizon_minutes!==[30,60,90][i] || !Number.isFinite(p.depth_cm) || !Number.isFinite(Date.parse(p.target_at))) || !Number.isFinite(next.adjusted?.depth_cm) || !Number.isFinite(next.initial_depth_cm) || !next.initialization_at || !Number.isFinite(Date.parse(next.valid_until??"")))throw Error("Projection response failed validation.");
          if(config.mode==="live" && next.rain_snapshot?.data_source!==config.rainSource)throw Error("Rain-gauge source did not match.");
          anchor=next.initialization_at;
          const tip=next.rain_snapshot?.latest_tip_event_id;
          newTip=tip!==undefined && lastTip!==undefined && tip>lastTip;
          lastTip=tip;
        }
        report(stationId,{data:next,error:"",newTip});
      }catch(error){if(!stopped && !signal.aborted)report(stationId,{data:null,newTip:false,error:error instanceof Error?error.message:"Projection unavailable."});if(!signal.aborted)throw error;}
    }
    const stop=visiblePoll(poll,config.mode==="live"?3000:15000);
    return ()=>{stopped=true;stop();};
  },[stationId,config,report]);
  return null;
}

export function HybridProjectionProvider({children}:{children:ReactNode}) {
  const {user}=useAccount();
  const {snapshot,error:monitoringError}=useMonitoring();
  const storageKey=projectionStorageKey(user.id);
  const [setups,setSetups]=useState<Record<string,Setup>>({});
  const [restoredKey,setRestoredKey]=useState("");
  const [results,setResults]=useState<Record<string,Result>>({});
  const [clock,setClock]=useState(0);
  const [viewers,setViewers]=useState<Record<string,number>>({});
  const subscribe=useCallback((station:string)=>{
    setViewers(old=>({...old,[station]:(old[station]??0)+1}));
    return()=>setViewers(old=>({...old,[station]:Math.max(0,(old[station]??1)-1)}));
  },[]);
  useEffect(()=>{const tick=()=>setClock(Date.now());tick();const timer=setInterval(()=>{if(!document.hidden)tick();},1000);document.addEventListener("visibilitychange",tick);return()=>{clearInterval(timer);document.removeEventListener("visibilitychange",tick);};},[]);
  useEffect(()=>{
    let restored:Record<string,Setup>={};
    try { restored=decodeProjectionSetups(localStorage.getItem(storageKey)); } catch { /* Storage can be disabled. */ }
    setSetups(restored);setResults({});setRestoredKey(storageKey);
    const sync=(event:StorageEvent)=>{
      if(event.key!==storageKey)return;
      const next=decodeProjectionSetups(event.newValue);
      setSetups(old=>encodeProjectionSetups(old)===encodeProjectionSetups(next)?old:next);
    };
    window.addEventListener("storage",sync);
    return()=>window.removeEventListener("storage",sync);
  },[storageKey]);
  useEffect(()=>{
    if(restoredKey!==storageKey)return;
    try { localStorage.setItem(storageKey,encodeProjectionSetups(setups)); } catch { /* Keep this session usable. */ }
  },[setups,restoredKey,storageKey]);
  useEffect(()=>{
    if(restoredKey!==storageKey || !snapshot)return;
    const source=snapshot.stations.find(station=>station.station_id==="STATION_001");
    const station=source?monitoringStationForDisplay(source,snapshot.checked_at,snapshot.stale_after_seconds,
      Date.now(),Boolean(monitoringError)):undefined;
    const localDemo=["localhost","127.0.0.1","[::1]"].includes(window.location.hostname);
    setSetups(old=>withAutomaticDemoSetup(old,station,localDemo));
  },[snapshot,monitoringError,restoredKey,storageKey]);
  const report=useCallback((station:string,result:Result)=>setResults(old=>({...old,[station]:result})),[]);
  function stop(station:string){setSetups(old=>({...old,[station]:{config:old[station]?.config??defaults,active:false}}));report(station,emptyResult);}
  function configure(station:string,patch:Partial<Configuration>){setSetups(old=>({...old,[station]:{config:{...(old[station]?.config??defaults),...patch},active:false}}));report(station,emptyResult);}
  function start(station:string){
    const config=setups[station]?.config??defaults;
    if(!config.confirmed || !config.initial.trim() || !Number.isFinite(Number(config.initial)))return;
    report(station,emptyResult);
    setSetups(old=>({...old,[station]:{config:old[station]?.config??defaults,active:true}}));
  }
  return <Context.Provider value={{setups,results,clock,configure,start,stop,subscribe}}>
    {Object.entries(setups).filter(([station,setup])=>setup.active && (viewers[station]??0)>0).map(([station,setup])=><ProjectionFeed key={station} stationId={station} config={setup.config} report={report}/>)}
    {children}
  </Context.Provider>;
}

export function useHybridProjection(station:string){
  const state=useContext(Context);
  if(!state)throw Error("useHybridProjection requires HybridProjectionProvider");
  useEffect(()=>state.subscribe(station),[station,state.subscribe]);
  const setup=state.setups[station]??{config:defaults,active:false};
  const result=state.results[station]??emptyResult;
  const expired=result.data?.status==="available" && state.clock>=Date.parse(result.data.valid_until??"");
  return {...setup,...result,clock:state.clock,expired,available:result.data?.status==="available" && !expired && !result.error,
    configure:(patch:Partial<Configuration>)=>state.configure(station,patch),start:()=>state.start(station),stop:()=>state.stop(station)};
}
