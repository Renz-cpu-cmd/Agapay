"use client";
import DeliveryConsole from "./DeliveryConsole";
import OperationsDetails from "./OperationsDetails";
import {useEvidenceClock} from "@/hooks/useEvidenceClock";
import type {OperationalDiagnostics} from "@/lib/operations-console";
import { useEffect,useState } from "react";
import { accountRequest } from "@/lib/accounts";
import { visiblePoll } from "@/lib/visible-poll";
import { useMonitoring } from "@/context/MonitoringContext";
import { measurementText, measurementNote } from "@/lib/measurements";
import type { HealthChannel } from "@/lib/channel-health";

function Channel({channel}:{channel?:HealthChannel}) {
  return <div><strong>{channel?.state ?? "unknown"}</strong><p>{channel?.value == null ? "—" : `${channel.value} ${channel.unit??""}`}</p>
    <p className="subtle-note">Observed {channel?.observed_at??"—"} · {channel?.age_seconds == null ? "Age unknown" : `${Math.floor(channel.age_seconds)} seconds old`}</p>
    <details><summary>Channel evidence</summary><p className="subtle-note">{channel?.reason??"Independent channel observation unavailable"}</p>
    {channel?.connection_state&&<p className="subtle-note">Subscriber: {channel.connection_state} · {channel.connection_observed_at??"Observation time unknown"} · {channel.observer_scope}</p>}
    </details>
  </div>;
}
export default function SystemHealth() {
  const {stations,snapshot,refresh,loading,error}=useMonitoring();
  const [operations,setOperations]=useState<OperationalDiagnostics|null>(null);
  const [operationsError,setOperationsError]=useState("");
  const now=useEvidenceClock();
  const [revision,setRevision]=useState(0);
  const diagnosticAge=operations?now-Date.parse(operations.checked_at):Infinity;
  const operationsKnown=!operationsError&&diagnosticAge>=0&&diagnosticAge<=45000;
  useEffect(()=>visiblePoll(async signal=>{
    try{const value=await accountRequest<NonNullable<typeof operations>>("operations/diagnostics","GET",undefined,signal);if(!signal.aborted){setOperations(value);setOperationsError("");}}
    catch(error){if(!signal.aborted)setOperationsError("Workflow diagnostics unavailable; readiness cannot be confirmed.");throw error;}
  },15000),[revision]);
  const active=stations.filter(s=>s.administrativeStatus==="active");
  const outages=active.filter(s=>s.channelHealth?.device_heartbeat.state==="stale");
  const counts=[
    ["Total stations",stations.length],["Active heartbeat healthy",active.filter(s=>s.channelHealth?.device_heartbeat.state==="healthy").length],
    ["Unexpected heartbeat outages",outages.length],["Awaiting first heartbeat",active.filter(s=>s.channelHealth?.device_heartbeat.state==="no_data").length],
    ["Active health unknown",active.filter(s=>!s.channelHealth||["unknown","unverified"].includes(s.channelHealth.device_heartbeat.state)).length],
    ["Maintenance",stations.filter(s=>s.administrativeStatus==="maintenance").length],
    ["Inactive",stations.filter(s=>s.administrativeStatus==="inactive").length],
  ];
  return <div className="design-page health-screen">
    <section>
    <div className="design-controls"><p className="subtle-note">Independent channel health{snapshot?` · Heartbeat expiry ${snapshot.stale_after_seconds}s · Rain-counter expiry 30s`:""}</p>
      <button className="design-button ml-auto" onClick={()=>void refresh()} disabled={loading}>{loading?"Refreshing…":"Refresh"}</button></div>
    {error&&<p role="status">Monitoring service unavailable; current health cannot be confirmed.</p>}
    <div className="card-grid grid-cols-3 health-summary">{counts.slice(0,3).map(([label,count])=><section key={label} className="design-panel p-4"><h2>{label}</h2><strong className="text-3xl">{count}</strong></section>)}</div>
    <div className="health-administrative-summary">{counts.slice(3).map(([label,count])=><section key={label}><h2>{label}</h2><strong>{count}</strong></section>)}</div>
    {outages.length>0&&<p role="status">{outages.length} active station(s) have stale device heartbeats. Maintenance, inactive and first-contact states are counted separately.</p>}
    <p className="subtle-note">A water heartbeat does not prove rain-counter operation. Zero tips is a valid counter value; unknown rain stays unavailable.</p>
    <div className="overflow-x-auto"><table className="w-full design-panel"><thead><tr>{["Station / administration","Device heartbeat","Water sensor","Rain counter / independent journal","Broker ingestion","Calibration"].map(label=><th className="text-left p-3" key={label}>{label}</th>)}</tr></thead><tbody>
      {stations.map(station=><tr key={station.id}>
        <td className="p-3"><strong>{station.name}</strong><p>{station.id} · {station.administrativeStatus??"unknown"}</p><details><summary>Lifecycle and notifications</summary><p>{station.lifecycle?.state??"Lifecycle unavailable"} · sensor push {station.lifecycle?.external_sensor_notifications?"enabled":"suppressed"}</p><p className="subtle-note">{station.lifecycle?.hazard_policy} · {station.lifecycle?.local_alarm_policy}</p></details></td>
        <td className="p-3"><Channel channel={station.channelHealth?.device_heartbeat}/></td>
        <td className="p-3"><Channel channel={station.channelHealth?.water_sensor}/><p>{measurementText(station.depth,1,"cm")}</p><details><summary>Depth quality and times</summary><p>{measurementNote(station.depth)}</p></details></td>
        <td className="p-3"><Channel channel={station.channelHealth?.rain_counter}/>{station.channelHealth?.rain_counter.increment_mm!=null&&<p>Last counter increment {station.channelHealth.rain_counter.increment_mm.toFixed(3)} mm</p>}</td>
        <td className="p-3"><Channel channel={station.channelHealth?.broker_ingestion}/></td>
        <td className="p-3"><strong>{station.channelHealth?.calibration.state??"unknown"}</strong><p>Rain: {station.channelHealth?.calibration.rain_configured_mm_per_tip??"—"} mm/tip</p><details><summary>Configuration</summary><p>Applied configuration: {station.configuration?.status??"unknown"} · revision {station.configuration?.revision??"—"}</p><p className="subtle-note break-all">Expected {station.configuration?.config_hash??"—"} · reported {station.configuration?.applied_config_hash??"—"}</p><p>Local outputs: {station.configuration?.local_alert_profile??"unknown"} · sensor fault: {station.configuration?.sensor_fault??"unknown"}</p><p>Review: {station.configuration?.validation_status??"unreviewed"}</p></details></td>
      </tr>)}
    </tbody></table></div></section>
<details className="design-panel p-4"><summary>Service workflows, delivery evidence and recovery</summary>    <header className="workspace-heading"><div><p className="workspace-eyebrow">Operations console</p><h1>Is the service working through to residents?</h1><p>Dependency readiness, queue progress and resident delivery evidence.</p></div><button className="design-button" onClick={()=>setRevision(n=>n+1)}>Refresh workflow diagnostics</button></header>
    <section className="design-panel p-4"><h2>Service workflows</h2><p className="subtle-note">Readiness covers configured required capabilities. Optional or disabled delivery does not establish an end-to-end service to residents.</p>
      <p role="status">{operationsError || (operations?(operationsKnown?`${operations.status} · readiness ${operations.ready?"ready":"degraded"} · checked ${operations.checked_at}`:`Diagnostics expired; readiness cannot be confirmed. Last checked ${operations.checked_at}`):"Waiting for dependency diagnostics")}</p>
      <div className="card-grid grid-cols-3">{operations?.components.map(component=><div key={component.name}><strong>{component.name}: {operationsKnown?component.state:`unknown (last reported ${component.state})`}</strong><p>{component.message}</p><p className="subtle-note">{component.code??(operationsKnown?"No active fault":"Current fault state unknown")} · {component.required?"Required capability":"Optional capability"}</p></div>)}</div>
      {operations?.alerts.map(alert=><p key={alert.code} role="status"><strong>{alert.code}</strong>  ·  {alert.message}</p>)}
    </section>
    {operations&&<OperationsDetails report={operations} known={operationsKnown} now={now}/>}
    <DeliveryConsole/>
</details>
  </div>;
}
