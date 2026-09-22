"use client";
import { useEffect, useState } from "react";
import type { Page } from "@/lib/navigation";
import { useMonitoring } from "@/context/MonitoringContext";
const titles: Record<Page,string> = { dashboard:"Live Monitoring Dashboard", stations:"Monitoring Stations", alerts:"Alert Management", sos:"SOS Beacons", analytics:"Analytics", health:"System Health", users:"User Management", settings:"Settings" };
export default function Header({current}:{current:Page}) {
  const { dataMode } = useMonitoring();
  const [now,setNow] = useState<Date|null>(null);
  useEffect(() => { setNow(new Date()); const timer = setInterval(() => setNow(new Date()),1000); return () => clearInterval(timer); },[]);
  const time = now?.toLocaleTimeString("en-PH",{hour:"2-digit",minute:"2-digit",second:"2-digit",timeZone:"Asia/Manila"});
  const date = now?.toLocaleDateString("en-PH",{month:"short",day:"numeric",year:"numeric",timeZone:"Asia/Manila"});
  const monitoringPage = ["dashboard","stations","alerts","analytics","health"].includes(current);
  const modeLabel = dataMode === "simulator" ? "SIMULATOR" : dataMode === "device" ? "LIVE" : dataMode === "no_data" ? "NO DATA" : "DEMO";
  const modeTitle = dataMode === "simulator" ? "Live readings from the AGAPAY virtual station" : dataMode === "device" ? "Live readings from a registered station" : dataMode === "no_data" ? "Connected, waiting for the first station reading" : "Station monitoring fallback data";
  return <header className="design-header"><h1>{titles[current]}</h1><div className="header-meta"><span className="connection-label" title={monitoringPage ? modeTitle : "Connected account service"}><i/>{current === "sos" ? "PRACTICE" : monitoringPage ? modeLabel : "ONLINE"}</span><time dateTime={now?.toISOString()}>{date ?? "—"}<b>·</b>{time ?? "—"}</time></div></header>;
}
