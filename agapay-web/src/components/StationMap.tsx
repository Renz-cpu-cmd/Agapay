"use client";

import dynamic from "next/dynamic";
import { useCallback, useState } from "react";
import { useMonitoring } from "@/context/MonitoringContext";
import { tierColor } from "@/data/mockData";
import { googleCityMapLink, stationCoordinates, type MapTileStatus } from "@/lib/station-map";

const GoogleStationMapCanvas = dynamic(() => import("./GoogleStationMapCanvas"), {
  ssr: false,
  loading: () => <div className="station-map-loading google-map-loading" role="status">Loading Google dark map…</div>,
});
const GooglePhotorealisticMapCanvas = dynamic(() => import("./GooglePhotorealisticMapCanvas"), {
  ssr: false,
  loading: () => <div className="station-map-loading google-map-loading" role="status">Loading photorealistic 3D map…</div>,
});

export default function StationMap({ onViewStation }: { onViewStation: (id: string) => void }) {
  const googleApiKey = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY ?? "";
  const googleMapId = process.env.NEXT_PUBLIC_GOOGLE_MAP_ID ?? "DEMO_MAP_ID";
  const { stations, dataMode } = useMonitoring();
  const [googleMode, setGoogleMode] = useState<"dark" | "3d">("3d");
  const [selectedId, setSelectedId] = useState("");
  const [tileStatus, setTileStatus] = useState<MapTileStatus>("loading");
  const [resetVersion, setResetVersion] = useState(0);
  const [mapVersion, setMapVersion] = useState(0);
  const selected = stations.find(station => station.id === selectedId);
  const mappedCount = stations.filter(station => stationCoordinates(station)).length;
  const mapStateKey = stations.map(station => `${station.id}:${station.status}:${station.isOnline}:${station.coordinates?.latitude ?? ""}:${station.coordinates?.longitude ?? ""}`).join("|");
  const handleFailure = useCallback(() => setTileStatus("error"), []);

  return <section className="station-map-panel" aria-labelledby="station-map-title">
    <header className="station-map-toolbar">
      <div><h2 id="station-map-title">STATION MAP</h2><p>Urdaneta City, Pangasinan <span className="station-map-provider google">Google {googleMode === "3d" ? "3D" : "Dark"}</span></p></div>
      <div className="station-map-actions">
        <button className="station-map-mode" onClick={() => { setTileStatus("loading"); setGoogleMode(mode => mode === "3d" ? "dark" : "3d"); }}>{googleMode === "3d" ? "Dark map" : "3D view"}</button>
        <select aria-label="Station on map" className="design-input" value={selectedId} onChange={event => setSelectedId(event.target.value)}>
          <option value="">City overview</option>
          {stations.map(station => <option key={station.id} value={station.id}>{station.id}{stationCoordinates(station) ? "" : " · Location pending"}</option>)}
        </select>
        <button className="design-button small" onClick={() => { setSelectedId(""); setResetVersion(value => value + 1); }}>Reset view</button>
      </div>
    </header>
    <div className="station-map-body">
      {!googleApiKey
        ? <div className="station-map-loading google-map-loading" role="status">Google Maps is not configured for this deployment.</div>
        : googleMode === "3d"
          ? <GooglePhotorealisticMapCanvas key={`google-3d-${mapVersion}-${mapStateKey}`} apiKey={googleApiKey} mapId={googleMapId} stations={stations} selectedStationId={selectedId} resetVersion={resetVersion} onSelectStation={setSelectedId} onStatusChange={setTileStatus} onFailure={handleFailure}/>
          : <GoogleStationMapCanvas key={`google-dark-${mapVersion}-${mapStateKey}`} apiKey={googleApiKey} mapId={googleMapId} stations={stations} selectedStationId={selectedId} resetVersion={resetVersion} onSelectStation={setSelectedId} onStatusChange={setTileStatus} onFailure={handleFailure}/>} 
      {googleApiKey && tileStatus === "loading" && <p role="status" className="station-map-progress">Loading map tiles…</p>}
      {(tileStatus === "error" || tileStatus === "partial") && <div role="status" className="station-map-notice">
        <strong>{tileStatus === "partial" ? "Some map tiles could not load" : "Map tiles could not load"}</strong>
        <p>Check your internet connection, then retry.</p>
        <div><button className="design-button small" onClick={() => { setTileStatus("loading"); setMapVersion(value => value + 1); }}>Retry map</button><a href={googleCityMapLink} target="_blank" rel="noopener noreferrer">Open full map</a></div>
      </div>}
    </div>
    <footer className="station-map-footer">
      {selected ? <>
        <div><strong>{selected.name}</strong><p>{stationCoordinates(selected) ? `${selected.coordinates?.status === "verified" ? "Confirmed" : "Planned"} location` : "Station coordinates have not been set."}<span style={{ color: tierColor[selected.status] }}> · Demo reading: {selected.waterLevel} cm</span></p></div>
        <button className="design-button small" onClick={() => onViewStation(selected.id)}>View station</button>
      </> : <>
        <div><strong>{mappedCount} of {stations.length} station locations set</strong><p>{dataMode === "simulator" ? "Pins and readings follow the virtual station feed." : mappedCount < stations.length ? "Station pins appear when their coordinates are added." : "Select a station pin to view its details."}</p></div>
        <span className="station-map-help">{googleMode === "3d" ? "Pinch to zoom · Drag to orbit · Dark map for terrain modes" : "Two-finger zoom · Map menu for terrain and satellite"}</span>
      </>}
    </footer>
  </section>;
}
