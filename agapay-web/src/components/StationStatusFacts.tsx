import type { Station } from "@/data/mockData";
import { stationStatusDescription } from "@/lib/station-map";

/** Visible words carry every dimension; map hue is only a secondary hint. */
export default function StationStatusFacts({station,compact=false}:{station:Station;compact?:boolean}) {
  if(compact) return <div className="station-status-summary">
    <span>Observation: {station.depth.state==="current"?station.observationTier??station.status:"UNKNOWN"}</span>
    <span>Episode: {station.activeHazardTier??"None recorded"}{station.hazardState==="unresolved"?" · unresolved":""}</span>
    <span>Heartbeat: {station.connectionStatus?.replaceAll("_"," ")??"unknown"} · {station.lastPing}</span>
    <span>Latest sample: {station.depth.latestSampleQuality}</span>
  </div>;
  return <p className="subtle-note station-status-facts">{stationStatusDescription(station)}</p>;
}
