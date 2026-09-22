"use client";

import { useEffect, useRef, useState } from "react";
import { useDialog } from "@/hooks/useDialog";
import { FigmaIcon } from "./DesignUI";
import { useSos } from "@/context/SosContext";
import { accountRequest } from "@/lib/accounts";
import { sosTime, type SosRequest, type SosStatus } from "@/lib/sos";
import GoogleSosLocationMap from "./GoogleSosLocationMap";

const statusColor: Record<SosStatus, string> = { ACTIVE: "#00ff24", ACKNOWLEDGED: "#f5df00", RESOLVED: "#00e83a" };
const panel = { background: "#00112e", border: "1px solid #002967", borderRadius: 4 };
const button = "px-4 py-2 font-ui text-xs font-bold rounded transition-opacity hover:opacity-80 disabled:opacity-50";
function Status({ status }: { status: SosStatus }) {
  return <span className="design-badge" style={{ color: statusColor[status], background: `${statusColor[status]}18` }}>{status}</span>;
}

function LocationMap({ item, initialShow = false }: { item: SosRequest; initialShow?: boolean }) {
  const [show, setShow] = useState(initialShow);
  if (item.latitude === null || item.longitude === null) return <p className="text-xs text-amber-400">Coordinates unavailable. Use the resident’s location description and contact details.</p>;
  const lat = item.latitude, lon = item.longitude;
  const live = item.location_source === "gps" && item.status !== "RESOLVED";
  const googleApiKey = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY ?? "";
  const googleMapId = process.env.NEXT_PUBLIC_GOOGLE_MAP_ID ?? "DEMO_MAP_ID";
  return <div className="flex flex-col gap-2">
    <p className="font-data text-xs text-slate-400">{lat.toFixed(6)}, {lon.toFixed(6)} · {item.location_source === "gps" ? `Device location · ±${Math.round(item.accuracy_m ?? 0)} m` : "Manually entered"}</p>
    {item.location_recorded_at && <p className="text-xs text-slate-500">Last device fix {sosTime(item.location_recorded_at)} PHT</p>}
    {live && <p className="text-xs font-bold text-green-400">● FOREGROUND LOCATION SHARING · Map refreshes about every 5 seconds</p>}
    {show ? <GoogleSosLocationMap key={`${lat}-${lon}`} apiKey={googleApiKey} mapId={googleMapId} latitude={lat} longitude={lon} label={`Location of practice SOS ${item.id}`}/> : <button className={button} style={{ background: "#001637", color: "#38bdf8" }} onClick={() => setShow(true)}>SHOW LOCATION ON MAP</button>}
    <a className="text-xs text-sky-400 underline" target="_blank" rel="noopener noreferrer" href={`https://www.google.com/maps/search/?api=1&query=${lat},${lon}`}>Open in Google Maps</a>
    <p className="text-xs text-slate-500">Online map · Coordinates are shared with Google Maps when opened. GPS updates arrive only while the resident keeps foreground sharing active.</p>
  </div>;
}

function SOSDetailModal({ initial, onClose, openMap }: { initial: SosRequest; onClose: () => void; openMap: boolean }) {
  const { update, refresh } = useSos();
  const dialogRef = useDialog(onClose);
  const [item, setItem] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const mutating = useRef(false);
  const generation = useRef(0);
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      if (!mutating.current) {
        const ticket = ++generation.current;
        try {
          const next = await accountRequest<SosRequest>(`sos/${initial.id}`);
          if (!stopped && ticket === generation.current) { setItem(next); setError(""); }
        } catch (e) {
          if (!stopped && ticket === generation.current) setError(e instanceof Error ? e.message : "Status refresh failed.");
        }
      }
      if (!stopped) timer = setTimeout(poll, 5000);
    }
    void poll();
    return () => { stopped = true; alive.current = false; ++generation.current; clearTimeout(timer); };
  }, [initial.id]);
  async function change(status: SosStatus) {
    if (mutating.current) return;
    mutating.current = true; ++generation.current; setBusy(true); setError("");
    try {
      const updated = await update(item.id, status, note);
      if (alive.current) setItem(updated);
    } catch (e) {
      if (alive.current) setError(`${e instanceof Error ? e.message : "Update failed."} The requested change has not been confirmed. Refresh before retrying.`);
      void refresh();
    } finally { mutating.current = false; if (alive.current) setBusy(false); }
  }
  return <div ref={dialogRef} role="dialog" aria-modal="true" aria-label="SOS details" tabIndex={-1} className="design-overlay">
    <div className="design-modal sos-detail">
      <div className="sos-detail-title">
        <FigmaIcon name="warning" size={28}/><h2 className="flex-1">PRACTICE SOS · #{item.id}</h2>
        <button aria-label="Close dialog" onClick={onClose} className="text-slate-400">✕</button>
      </div>
      <div className="sos-detail-body">
        <p className="text-xs text-amber-400">Development exercise. Saving or acknowledging this request does not dispatch emergency responders.</p>
        <div className="grid grid-cols-2 gap-3">
          {[["Resident", item.resident_name], ["Phone", item.phone], ["Barangay", item.barangay], ["Location", item.location], ["Received (PHT)", sosTime(item.created_at)]].map(([k,v]) => <div key={k} className="min-w-0"><p className="text-xs text-slate-500">{k}</p><p className="font-ui text-xs font-bold text-slate-300 break-words whitespace-pre-wrap">{v}</p></div>)}
        </div>
        <p className="p-3 text-xs text-slate-400 whitespace-pre-wrap break-words" style={{ ...panel, background: "#001434" }}>{item.message || "No additional message."}</p>
        <div className="flex justify-between items-center"><span className="text-xs text-slate-500">Status</span><Status status={item.status}/></div>
        <div className="text-xs text-slate-400 flex flex-col gap-2 border-l-2 border-slate-700 pl-3">
          <p>Received · {sosTime(item.created_at)} PHT</p>
          {item.acknowledged_at && <p>Acknowledged · {item.acknowledged_by_name} · {sosTime(item.acknowledged_at)} PHT</p>}
          {item.resolved_at && <p>Resolved · {item.resolved_by_name} · {sosTime(item.resolved_at)} PHT</p>}
          {item.resolution_note && <p className="whitespace-pre-wrap break-words">Resolution: {item.resolution_note}</p>}
        </div>
        <LocationMap item={item} initialShow={openMap}/>
        {item.status === "ACKNOWLEDGED" && <label className="text-xs text-slate-400">Resolution note (optional)<textarea maxLength={500} value={note} disabled={busy} onChange={(e) => setNote(e.target.value)} className="mt-2 w-full rounded border border-slate-700 bg-slate-950 p-2" rows={2}/></label>}
        {error && <p role="alert" className="text-xs text-red-400">{error}</p>}
        <div className="flex gap-3">
          {item.status === "ACTIVE" && <button disabled={busy} onClick={() => void change("ACKNOWLEDGED")} className={`${button} flex-1`} style={{ background: "#f5df00", color: "#000" }}>{busy ? "SAVING…" : "ACKNOWLEDGE"}</button>}
          {item.status === "ACKNOWLEDGED" && <button disabled={busy} onClick={() => void change("RESOLVED")} className={`${button} flex-1`} style={{ background: "#00e83a", color: "#000" }}>{busy ? "SAVING…" : "MARK RESOLVED"}</button>}
          <button onClick={onClose} className={button} style={{ background: "#001637", color: "#94a3b8" }}>CLOSE</button>
        </div>
      </div>
    </div>
  </div>;
}

export default function SOSBeacons() {
  const { page, filter, setFilter, error, syncedAt, loading, refresh, loadMore, update } = useSos();
  const [selected,setSelected]=useState<SosRequest|null>(null),[openMap,setOpenMap]=useState(false);
  const [pending,setPending]=useState<number|null>(null),[actionError,setActionError]=useState("");
  const pendingRef=useRef(false),items=page?.items??[];
  async function acknowledge(item:SosRequest) {
    if(pendingRef.current)return;pendingRef.current=true;setPending(item.id);setActionError("");
    try{await update(item.id,"ACKNOWLEDGED","");}
    catch(e){setActionError((e instanceof Error?e.message:"Update failed.")+" Acknowledgement has not been confirmed. Refresh before retrying.");void refresh();}
    finally{pendingRef.current=false;setPending(null);}
  }
  function view(item:SosRequest,map=false){setOpenMap(map);setSelected(item);}
  return <div className="design-page sos-screen">
    <p className="subtle-note">Practice mode · Requests are saved to AGAPAY. External emergency dispatch and push notifications are not connected.</p>
    {!!page?.counts.ACTIVE&&<div className="danger-banner"><FigmaIcon name="warning" size={24}/>● {page.counts.ACTIVE} ACTIVE PRACTICE SOS REQUEST{page.counts.ACTIVE===1?"":"S"} · Awaiting staff review</div>}
    <div className="design-toolbar"><div className="design-controls">{(["ALL","ACTIVE","ACKNOWLEDGED","RESOLVED"] as const).map(f=><button key={f} className={`design-button ${filter===f?"active":""}`} aria-pressed={filter===f} onClick={()=>setFilter(f)}>{f} {page&&(f==="ALL"?Object.values(page.counts).reduce((a,b)=>a+b,0):page.counts[f])}</button>)}</div><button disabled={loading} className="design-button" onClick={()=>void refresh()}>{loading?"REFRESHING…":"REFRESH"}</button></div>
    {(error||actionError)&&<p role="alert" className="form-error">{actionError||error}</p>}
    <div className="design-table-wrap"><table className="design-table"><thead><tr>{["ID","Resident","Location","Received (PHT)","Status","Action"].map(h=><th key={h}>{h}</th>)}</tr></thead><tbody>{items.map(item=><tr key={item.id}><td>SOS-{String(item.id).padStart(3,"0")}</td><td>{item.resident_name}</td><td className="max-w-72 break-words">{item.location}<small>{item.barangay}</small></td><td>{sosTime(item.created_at)}</td><td><Status status={item.status}/></td><td><button className={`design-button small ${item.status==="ACTIVE"?"danger":""}`} onClick={()=>view(item)}>{item.status==="ACTIVE"?"RESPOND":"View"}</button></td></tr>)}{!items.length&&<tr><td colSpan={6} className="design-empty">{loading?"Loading requests…":error?"Requests unavailable. Refresh when connected.":"No practice requests in this view."}</td></tr>}</tbody></table></div>
    {page&&items.length<page.total&&<button className="design-button" disabled={loading} onClick={loadMore}>LOAD MORE · {items.length} of {page.total}</button>}
    {items.filter(item=>item.status==="ACTIVE").map(item=><article key={item.id} className="danger-banner sos-request-card">
      <header className="flex justify-between gap-4"><div className="flex gap-2 items-center"><FigmaIcon name="warning" size={24}/>NEW PRACTICE SOS REQUEST</div><small className="text-right text-slate-400">{sosTime(item.created_at)}<br/>SOS-{String(item.id).padStart(3,"0")}</small></header>
      <p className="text-xs text-slate-400">{item.resident_name} · {item.location}</p><p className="text-xs text-slate-400 break-words whitespace-pre-wrap">“{item.message||"No additional message."}”</p>
      <div className="dialog-actions mt-0"><button className="design-button primary" onClick={()=>view(item,true)}>VIEW ON MAP</button><button className="design-button yellow" disabled={pending!==null} onClick={()=>void acknowledge(item)}>{pending===item.id?"SAVING…":"ACKNOWLEDGE"}</button></div>
    </article>)}
    <p className="subtle-note">{syncedAt?`Last synced ${sosTime(syncedAt)} PHT · Updates every 5 seconds`:"Connecting to SOS service…"}</p>
    {selected&&<SOSDetailModal key={selected.id} initial={selected} openMap={openMap} onClose={()=>setSelected(null)}/>}
  </div>;
}

