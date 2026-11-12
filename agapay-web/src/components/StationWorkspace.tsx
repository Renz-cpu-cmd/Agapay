"use client";
import {useState} from "react";
import Link from "next/link";
import {useMonitoring} from "@/context/MonitoringContext";
import {useAlertResource} from "@/hooks/useAlertResource";
import {useEvidenceClock} from "@/hooks/useEvidenceClock";
import {alertTime} from "@/lib/alerts";
import {elapsedLabel,readIsCurrent,reviewAction,type StationWorkspace as Workspace} from "@/lib/staff-workspaces";
import type {HealthChannel} from "@/lib/channel-health";
import type {Station} from "@/data/mockData";
import StationAdministration from "./StationAdministration";
import RainfallActivityPanel from "./RainfallActivityPanel";
import ForecastPanel from "./ForecastTrendPanel";
import StationStatusFacts from "./StationStatusFacts";
import MeasuredTrend from "./MeasuredTrend";

function ChannelEvidence({label,channel}:{label:string;channel?:HealthChannel}){
  return <div className="channel-evidence"><h3>{label}</h3><strong>{channel?.state??"unknown"}</strong><p>{channel?.reason??"Independent observation unavailable"}</p><p className="subtle-note">Observed {alertTime(channel?.observed_at??null)} · {channel?.age_seconds==null?"Age unknown":`${Math.floor(channel.age_seconds)}s old`}</p>{channel?.connection_state&&<p>Subscriber {channel.connection_state} · {channel.observer_scope??"Scope unknown"}</p>}</div>;
}
type Policy={state?:string;version:number;evidence:string;rules:Record<string,unknown>};
export default function StationWorkspace({station,onBack}:{station:Station;onBack:()=>void}){
  const {snapshot,error,refresh}=useMonitoring();
  const [offset,setOffset]=useState(0),[revision,setRevision]=useState(0);
  const workspaceRead=useAlertResource<Workspace>(`stations/${encodeURIComponent(station.id)}/workspace?limit=20&offset=${offset}&refresh=${revision}`);
  const stationMismatch=Boolean(workspaceRead.data&&workspaceRead.data.station_id!==station.id);
  const resource={...workspaceRead,data:stationMismatch?null:workspaceRead.data,error:workspaceRead.error||stationMismatch};
  const policy=useAlertResource<Policy>(`stations/${encodeURIComponent(station.id)}/hazard-policy`);
  const now=useEvidenceClock(),current=readIsCurrent(resource.data?.checked_at,now)&&!resource.error;
  const evidence=resource.data,identity=evidence?.identity,config=station.configuration;
  const recorded=[{label:"Latest eligible sample measured",value:evidence?.latest_sample?.measured_at},
    {label:"That sample received",value:evidence?.latest_sample?.received_at},
    {label:"Last valid depth measured",value:evidence?.last_valid?.measured_at},
    {label:"Last valid depth received",value:evidence?.last_valid?.received_at},
    {label:"Latest packet received (includes historical / rejected-for-current)",value:evidence?.latest_received?.received_at},
    {label:"Device heartbeat",value:station.heartbeatAt}];
  return <div className="design-page station-detail-screen staff-decisions">
    <header className="workspace-heading"><div><button className="design-button" onClick={onBack}>Back to stations</button><p className="workspace-eyebrow">Station workspace · {station.id}</p><h1>{station.name}</h1><p>{station.location}</p></div><button className="design-button" onClick={()=>{setRevision(n=>n+1);void refresh();}}>Refresh reading evidence</button></header>
    <section className="design-panel p-4" aria-labelledby="reading-trust-title"><h2 id="reading-trust-title">Can this reading be trusted?</h2><p className="next-action"><strong>Next check:</strong> {reviewAction(station)}</p>
      <StationStatusFacts station={station}/>
      <p className="subtle-note">An unresolved historical hazard is not a new observation. A heartbeat does not refresh the last-valid depth.</p>
      {error&&<p role="status">Monitoring unavailable; channel and depth values are last-known.</p>}
      {resource.loading&&<p role="status">Checking identity and sample evidence…</p>}{resource.error&&<p role="alert">Reading evidence unavailable. Identity, timing and log state cannot be confirmed.</p>}
      {evidence&&<p role="status">{current?"Registry and sample evidence checked":"Last-known registry and sample evidence"} {alertTime(evidence.checked_at)}</p>}
      <dl className="evidence-grid"><div><dt>Provisioned device identity</dt><dd>{identity?`${identity.device_id} · identity version ${identity.version} · ${identity.state}`:"Unavailable; no identity confirmation"}</dd></div>
        <div><dt>Last-valid sample ingress identity</dt><dd>{evidence?.last_valid?`${evidence.last_valid.source_id??"Unverified"} · registry ${evidence.last_valid.registry_version??"unknown"} · ${evidence.last_valid.transport??"Transport unknown"}`:"No valid sample recorded"}</dd></div>
        <div><dt>Source trust now</dt><dd>Latest source: {station.sourceTrusted?"Registry-verified physical source":"Unverified / unavailable"}<p>Retained depth: {station.depthSourceTrusted?"Registry-verified physical source":"Unverified / unavailable"} · {station.depthSourceId??"Identity unknown"}</p></dd></div>
        <div><dt>Coordinates / reference datum</dt><dd>{identity?`${identity.coordinates_verified?"Verified coordinates":"Coordinates unverified"} · ${identity.datum}`:"No commissioning record available"}</dd></div>
        <div><dt>Configuration agreement</dt><dd>{config?.status??"unknown"} · revision {config?.revision??"—"} · {config?.validation_status??"unreviewed"}</dd></div>
        <div><dt>Local outputs / sensor fault</dt><dd>{config?.local_alert_profile??"unknown"} / {config?.sensor_fault??"unknown"}</dd></div>
        <div><dt>Expected configuration hash</dt><dd className="hash-value">{config?.config_hash??"Not configured"}</dd></div><div><dt>Device-reported applied hash</dt><dd className="hash-value">{config?.applied_config_hash??"Not reported"}</dd></div>
        <div><dt>Firmware version (reported metadata)</dt><dd>{station.firmware}</dd></div><div><dt>Administration</dt><dd>{station.lifecycle?.state??station.administrativeStatus??"unknown"} · external sensor notifications {station.lifecycle?station.lifecycle.external_sensor_notifications?"enabled":"suppressed":"unknown"}</dd></div>
      </dl>
    </section>
    <section className="design-panel p-4"><h2>Measurement and receipt times</h2><dl className="evidence-grid">{recorded.map(row=><div key={row.label}><dt>{row.label}</dt><dd>{alertTime(row.value??null)}<p className="subtle-note">{elapsedLabel(row.value,now)}</p></dd></div>)}</dl><p>Latest received disposition: {evidence?.latest_received?.disposition??"unknown"} · latest eligible quality: {evidence?.latest_sample?.quality??"unknown"}</p><p className="subtle-note">All times PHT. Packet receipt includes late/backfilled records and cannot prove a new measurement. Missing measured times remain unknown.</p></section>
    <section className="design-panel p-4"><h2>Independent channel health</h2><div className="channel-evidence-grid"><ChannelEvidence label="Water sensor" channel={station.channelHealth?.water_sensor}/><ChannelEvidence label="Rain counter" channel={station.channelHealth?.rain_counter}/><ChannelEvidence label="Device heartbeat" channel={station.channelHealth?.device_heartbeat}/><ChannelEvidence label="Broker ingestion" channel={station.channelHealth?.broker_ingestion}/></div></section>
    <section className="design-panel p-4"><h2>Measured history and gaps</h2><MeasuredTrend station={station} maximumGapSeconds={snapshot?.stale_after_seconds??30}/><Link href="/analytics">Open bounded history and reports for a longer interval</Link></section>
    <div className="staff-overview-grid"><section className="design-panel p-4"><h2>Configured sensor thresholds</h2><p>{station.hazardPolicyState==="station_reviewed"?"Station-reviewed recovery policy":"Provisional recovery policy; physical review pending"}</p><dl className="evidence-grid">{Object.entries(station.thresholds).map(([tier,value])=><div key={tier}><dt>{tier}</dt><dd>{value} cm</dd></div>)}</dl><p className="subtle-note">These are sensor thresholds. Official authority actions and their effective/expiry times appear in authority notices.</p>
      {policy.error&&<p role="status">Recovery policy evidence unavailable.</p>}{policy.data&&<details><summary>Recovery rules and review evidence · version {policy.data.version}</summary><p>{policy.data.evidence}</p><dl className="evidence-grid">{Object.entries(policy.data.rules).map(([key,value])=><div key={key}><dt>{key.replaceAll("_"," ")}</dt><dd>{String(value)}</dd></div>)}</dl></details>}<Link href="/alerts">Review authority notices</Link>
    </section><section className="design-panel p-4"><h2>Calibration and commissioning evidence</h2><p>{identity?.calibration_note??"Calibration record unavailable"}</p><p>Commissioned {alertTime(identity?.commissioned_at??null)}</p><p>Rain coefficient: {station.channelHealth?.calibration.rain_configured_mm_per_tip??"—"} mm/tip</p><p>{station.channelHealth?.calibration.reason??"Calibration state unknown"}</p><p>Physical validation: {station.channelHealth?.calibration.physical_validation??"unconfirmed"}</p><p className="subtle-note">Recorded documentation and configuration agreement do not establish measured physical accuracy.</p></section></div>
    <section className="design-panel p-4"><h2>Calibration, maintenance and configuration log</h2><p className="subtle-note">Recorded station audit actions; no log entry is invented for an unrecorded field visit.</p>{evidence&&<><ol className="station-event-list">{evidence.events.map(event=><li key={event.id}><h3>{event.action.replaceAll("_"," ")}</h3><p>{event.actor} · {alertTime(event.created_at)}</p><p>{event.reason}</p></li>)}</ol>{!evidence.events.length&&<p>No station audit actions in this window.</p>}<div className="design-controls"><button className="design-button" disabled={!offset} onClick={()=>setOffset(Math.max(0,offset-20))}>Newer log entries</button><span>{evidence.total} recorded action(s)</span><button className="design-button" disabled={!evidence.has_more} onClick={()=>setOffset(offset+20)}>Older log entries</button></div></>}</section>
    <RainfallActivityPanel stationId={station.id}/>
    <details className="design-panel p-4"><summary>Manage lifecycle and station metadata</summary><StationAdministration key={station.id} stationId={station.id} onSaved={()=>{void refresh();setRevision(n=>n+1);}}/></details>
    <section className="design-panel p-4"><h2>Published forecast · separate from observed measurements</h2><ForecastPanel key={station.id} stationId={station.id}/><Link href="/ml-configuration">Private experimental ML workspace</Link></section>
  </div>;
}
