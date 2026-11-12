"use client";
import {useEffect,useState} from "react";
import {accountRequest} from "@/lib/accounts";
type Preferences={revision:number;locale:"en";resident_area_id:string|null;resident_area_name:string|null;requested_language:string|null};
export default function GeographicPreferences(){
  const [data,setData]=useState<Preferences|null>(null),[areas,setAreas]=useState<{id:string;name:string}[]>([]),[error,setError]=useState(""),[busy,setBusy]=useState(false),[conflicted,setConflicted]=useState(false),[language,setLanguage]=useState("");
  async function load(){if(busy)return;setBusy(true);setConflicted(true);try{setError("");const p=await accountRequest<Preferences>("preferences");setData(p);setLanguage(p.requested_language??"");setConflicted(false);const list=await accountRequest<typeof areas>("preferences/areas");setAreas(list);}catch(e){setError(e instanceof Error?e.message:"Preferences unavailable");}finally{setBusy(false);}}
  useEffect(()=>{void load();},[]);
  async function save(changes:Record<string,unknown>){if(!data||busy||conflicted)return;setBusy(true);setError("");try{setData(await accountRequest<Preferences>("preferences","PATCH",{expected_revision:data.revision,...changes}));}catch(e){setError(e instanceof Error?e.message:"Save failed");setConflicted(true);}finally{setBusy(false);}}
  const selected=areas.some(a=>a.id===data?.resident_area_id)?data?.resident_area_id??"":"";
  return <section className="design-panel p-4 flex flex-col gap-3"><h2>Geographic context and language</h2><p>Operational language: English. Filipino translation unavailable.</p><p className="subtle-note">Profile locality, verified resident area and selected monitoring station are separate. Area selection does not subscribe devices or establish flood exposure.</p>
    <label className="flex flex-col gap-1">Verified resident area<select className="design-input" disabled={!data||busy||conflicted||!areas.length} value={selected} onChange={e=>void save({resident_area_id:e.target.value||null})}><option value="">No verified area selected</option>{areas.map(a=><option key={a.id} value={a.id}>{a.name} · {a.id}</option>)}</select></label><p>{data?.resident_area_name??"No verified area"} · ID {data?.resident_area_id??"—"}</p>
    <form onSubmit={e=>{e.preventDefault();void save({requested_language:language.trim()||null});}}><label className="flex flex-col gap-1">Which language would help your community?<input className="design-input" maxLength={80} value={language} onChange={e=>setLanguage(e.target.value)}/></label><p className="subtle-note">Saves a language request; it does not change operational content.</p><button className="design-button" disabled={!data||busy||conflicted}>Save language request</button></form>
    {error&&<p role="alert">{error}</p>}<button className="design-button" disabled={busy} onClick={()=>void load()}>Refresh preferences; review before saving</button>
  </section>;
}
