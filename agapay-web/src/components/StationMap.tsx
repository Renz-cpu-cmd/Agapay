"use client";
import { measurementLabel, measurementText, measurementNote } from "@/lib/measurements";

import dynamic from "next/dynamic";
import { useCallback, useState } from "react";
import { useTheme } from "@/context/ThemeContext";
import { useMonitoring } from "@/context/MonitoringContext";
import StationStatusFacts from "./StationStatusFacts";
import { googleCityMapLink, locationLabel, stationCoordinates, type MapTileStatus } from "@/lib/station-map";
import { isLive, liveLabel } from "@/lib/live-position";

const GoogleStationMapCanvas = dynamic(() => import("./GoogleStationMapCanvas"), {
  ssr: false,
  loading: () => <div className="station-map-loading google-map-loading" role="status">Loading Google map…</div>,
});
const GooglePhotorealisticMapCanvas = dynamic(() => import("./GooglePhotorealisticMapCanvas"), {
  ssr: false,
  loading: () => <div className="station-map-loading google-map-loading" role="status">Loading photorealistic 3D map…</div>,
});

export default function StationMap({ onViewStation, selectedStationId, onSelectStation }: {
  onViewStation: (id: string) => void; selectedStationId: string; onSelectStation: (id: string) => void;
}) {
  const { theme } = useTheme();
  const googleApiKey = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY ?? "";
  const googleMapId = process.env.NEXT_PUBLIC_GOOGLE_MAP_ID ?? "DEMO_MAP_ID";
  const { stations, dataMode } = useMonitoring();
  const [googleMode, setGoogleMode] = useState<"map" | "3d">("map");
  const selectedId = selectedStationId;
  const setSelectedId = onSelectStation;
  const [tileStatus, setTileStatus] = useState<MapTileStatus>("loading");
  const [resetVersion, setResetVersion] = useState(0);
  const [mapVersion, setMapVersion] = useState(0);
  const [follow, setFollow] = useState(false);
  const selected = stations.find(station => station.id === selectedId);
  const selectedLive = selected?.livePosition ?? null;
  const following = follow && googleMode === "map" && Boolean(selectedLive);
  const mappedCount = stations.filter(station => stationCoordinates(station)).length;
  const mapStateKey = stations.map(station => `${station.id}:${station.status}:${station.isOnline}:${station.depthStatus}:${station.coordinates?.latitude ?? ""}:${station.coordinates?.longitude ?? ""}`).join("|");
  const handleFailure = useCallback(() => setTileStatus("error"), []);

  return <section className="station-map-panel" aria-labelledby="station-map-title">
    <header className="station-map-toolbar">
      <div><h2 id="station-map-title">STATION MAP</h2><p>Urdaneta City, Pangasinan <span className="station-map-provider google">Google {googleMode === "3d" ? "3D" : theme === "dark" ? "Dark" : "Default"}</span></p></div>
      <div className="station-map-actions">
        <button className="station-map-mode" onClick={() => { setTileStatus("loading"); setGoogleMode(mode => mode === "3d" ? "map" : "3d"); }}>{googleMode === "3d" ? "Theme map" : "3D view"}</button>
        {selectedLive && googleMode === "map" && <button className="design-button small" aria-pressed={following} onClick={() => setFollow(value => !value)}>{following ? "Following station" : "Follow station"}</button>}
        <select aria-label="Station on map" className="design-input" value={selectedId} onChange={event => { setFollow(false); setSelectedId(event.target.value); }}>
          <option value="">City overview</option>
          {stations.map(station => <option key={station.id} value={station.id}>{station.id}{stationCoordinates(station) ? "" : " · Location pending"}</option>)}
        </select>
        <button className="design-button small" onClick={() => { setFollow(false); setSelectedId(""); setResetVersion(value => value + 1); }}>Reset view</button>
      </div>
    </header>
    <div className="station-map-body">
      {!googleApiKey
        ? <div className="station-map-loading google-map-loading" role="status">Google Maps is not configured for this deployment.</div>
        : googleMode === "3d"
          ? <GooglePhotorealisticMapCanvas key={`google-3d-${mapVersion}-${mapStateKey}`} apiKey={googleApiKey} mapId={googleMapId} stations={stations} selectedStationId={selectedId} resetVersion={resetVersion} onSelectStation={setSelectedId} onStatusChange={setTileStatus} onFailure={handleFailure}/>
          : <GoogleStationMapCanvas key={`google-map-${mapVersion}-${mapStateKey}`} apiKey={googleApiKey} mapId={googleMapId} stations={stations} selectedStationId={selectedId} resetVersion={resetVersion} followStationId={following ? selectedId : ""} onSelectStation={setSelectedId} onStatusChange={setTileStatus} onFailure={handleFailure}/>}
      {googleApiKey && tileStatus === "loading" && <p role="status" className="station-map-progress">Loading map tiles…</p>}
      {(tileStatus === "error" || tileStatus === "partial") && <div role="status" className="station-map-notice">
        <strong>{tileStatus === "partial" ? "Some map tiles could not load" : "Map tiles could not load"}</strong>
        <p>Check your internet connection, then retry.</p>
        <div><button className="design-button small" onClick={() => { setTileStatus("loading"); setMapVersion(value => value + 1); }}>Retry map</button><a href={googleCityMapLink} target="_blank" rel="noopener noreferrer">Open full map</a></div>
      </div>}
    </div>
    <footer className="station-map-footer">
      {selected ? <>
        <div><strong>{selected.name}</strong>{selectedLive && <p className={`live-position-label ${isLive(selectedLive) ? "live" : "stale"}`} role="status">{liveLabel(selectedLive)}</p>}<p>{locationLabel(selected)} · {measurementLabel(selected.depth)}{selected.depth.value!==null?` · ${measurementText(selected.depth,1,"cm")} · ${selected.measurementAge??"Age unknown"}`:""}</p><StationStatusFacts station={selected} compact/><p>{selected.sourceTrusted&&selected.depthSourceTrusted?"Authenticated registered device":"Unverified / test source"}</p></div>
        <details className="station-evidence"><summary>Measurement evidence</summary><p>{measurementNote(selected.depth)}</p><StationStatusFacts station={selected}/></details>
        <button className="design-button small" onClick={() => onViewStation(selected.id)}>View station</button>
      </> : <>
        <div><strong>{mappedCount} of {stations.length} station locations set</strong><p>{dataMode === "simulator" ? "Pins and readings follow the virtual station feed." : mappedCount < stations.length ? "Station pins appear when their coordinates are added." : "Select a station pin to view its details."}</p></div>
        <span className="station-map-help">{googleMode === "3d" ? "Pinch to zoom · Drag to orbit · Theme map for terrain modes" : "Two-finger zoom · Map menu for terrain and satellite"}</span>
      </>}
    </footer>
  </section>;
}
