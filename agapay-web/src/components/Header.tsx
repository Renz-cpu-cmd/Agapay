"use client";
import { useEffect, useState } from "react";
import type { Page } from "@/lib/navigation";
import { useMonitoring } from "@/context/MonitoringContext";
import { monitoringSourceIsFresh } from "@/lib/monitoring";
const titles: Record<Page,string> = { dashboard:"Dashboard", stations:"Stations", resources:"Shelters & Access Sources", alerts:"Alert Management", sos:"SOS", analytics:"Analytics", forecasts:"Forecast Workspace", health:"System Health", users:"User Management", settings:"Settings", mlConfiguration:"ML Configuration", mlEvaluation:"ML Evaluation" };
export default function Header({current}:{current:Page}) {
  const { dataMode, snapshot, error, loading } = useMonitoring();
  const [now,setNow] = useState<Date|null>(null);
  useEffect(() => { setNow(new Date()); const timer = setInterval(() => setNow(new Date()),1000); return () => clearInterval(timer); },[]);
  const time = now?.toLocaleTimeString("en-PH",{hour:"2-digit",minute:"2-digit",second:"2-digit",timeZone:"Asia/Manila"});
  const date = now?.toLocaleDateString("en-PH",{month:"short",day:"numeric",year:"numeric",timeZone:"Asia/Manila"});
  const monitoringPage = ["dashboard","stations","analytics","health"].includes(current);
  const feedFresh = monitoringSourceIsFresh(snapshot, dataMode === "simulator" ? "simulator" : "device", now?.getTime() ?? Date.now(), Boolean(error));
  const hasKnownDepth = snapshot?.stations.some(station=>typeof station.current_depth_cm === "number");
  const modeLabel = loading ? "Checking readings" : dataMode === "simulator" ? "Virtual station feed" : dataMode === "device" ? feedFresh ? "Observed" : hasKnownDepth ? "Last known" : "No valid reading" : dataMode === "unverified" ? "Unregistered source" : "No valid reading";
  const modeTitle = dataMode === "device" || dataMode === "simulator" ? !feedFresh ? "Current valid depth is unconfirmed; inspect heartbeat, measurement quality and independent channel health" : dataMode === "simulator" ? "Live readings from the AGAPAY virtual station" : "Fresh valid depth from a registry-verified physical source" : dataMode === "no_data" ? "Connected, waiting for the first station reading" : "Station monitoring fallback data";
  return <header className="design-header"><h1>{titles[current]}</h1><div className="header-meta">{["alerts","forecasts","health"].includes(current) ? <span className="subtle-note" title="Persistent operational sensor episodes; unresolved hazards can outlast fresh measurements">{current==="forecasts"?"PUBLICATION EVIDENCE":current==="health"?"WORKFLOW DIAGNOSTICS":"SENSOR EPISODES"}</span> : <span className="connection-label" data-state={current==="sos"||dataMode==="simulator"?"exercise":monitoringPage ? feedFresh ? "current" : "unknown" : "account"} title={monitoringPage ? modeTitle : "Connected account service"}><i/>{current === "sos" ? "SOS requests" : monitoringPage ? modeLabel : "Signed in"}</span>}<time dateTime={now?.toISOString()}>{date ?? "—"}<b>·</b>{time ?? "—"}</time></div></header>;
}
