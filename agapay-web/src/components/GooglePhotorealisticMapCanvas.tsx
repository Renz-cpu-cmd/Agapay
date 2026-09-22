"use client";

import { useEffect, useRef } from "react";
import { tierColor, type Station } from "@/data/mockData";
import { loadGoogle3DLibraries } from "@/lib/google-maps";
import { cityMapCenter, stationCoordinates, type MapTileStatus } from "@/lib/station-map";

type Props = {
  apiKey: string;
  mapId: string;
  stations: Station[];
  selectedStationId: string;
  resetVersion: number;
  onSelectStation: (id: string) => void;
  onStatusChange: (status: MapTileStatus) => void;
  onFailure: () => void;
};

function focus3D(map: google.maps.maps3d.Map3DElement, stations: Station[], stationId: string) {
  const station = stations.find(item => item.id === stationId);
  const point = station && stationCoordinates(station);
  map.center = point
    ? { lat: point[0], lng: point[1], altitude: 0 }
    : { lat: cityMapCenter[0], lng: cityMapCenter[1], altitude: 0 };
  map.range = point ? 950 : 6800;
  map.tilt = point ? 67 : 58;
  map.heading = point ? 25 : 335;
}

export default function GooglePhotorealisticMapCanvas({
  apiKey,
  mapId,
  stations,
  selectedStationId,
  resetVersion,
  onSelectStation,
  onStatusChange,
  onFailure,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<google.maps.maps3d.Map3DElement | null>(null);
  const selectedStationRef = useRef(selectedStationId);

  useEffect(() => { selectedStationRef.current = selectedStationId; }, [selectedStationId]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    let disposed = false;
    let map: google.maps.maps3d.Map3DElement | null = null;
    let readyTimer: ReturnType<typeof setTimeout> | undefined;
    const authWindow = window as typeof window & { gm_authFailure?: () => void };
    const previousAuthFailure = authWindow.gm_authFailure;
    const fail = () => { if (!disposed) onFailure(); };
    authWindow.gm_authFailure = fail;
    onStatusChange("loading");

    loadGoogle3DLibraries(apiKey).then(({ maps3d, marker }) => {
      if (disposed || !containerRef.current) return;
      const { GestureHandling, Map3DElement, MapMode, Marker3DInteractiveElement } = maps3d;
      const { PinElement } = marker;
      map = new Map3DElement({
        center: { lat: cityMapCenter[0], lng: cityMapCenter[1], altitude: 0 },
        range: 6800,
        tilt: 58,
        heading: 335,
        mode: MapMode.HYBRID,
        gestureHandling: GestureHandling.GREEDY,
        mapId: mapId || "DEMO_MAP_ID",
        description: "Interactive photorealistic 3D map of Urdaneta City",
      });
      map.className = "google-photorealistic-map";
      map.addEventListener("gmp-error", fail);
      map.addEventListener("gmp-map-id-error", fail);
      map.addEventListener("gmp-steadychange", event => {
        if (!disposed && event.isSteady) onStatusChange("ready");
      });
      containerRef.current.append(map);
      mapRef.current = map;

      stations.forEach(station => {
        const point = stationCoordinates(station);
        if (!point || !map) return;
        const status = station.isOnline ? station.status : "OFFLINE";
        const pin = new PinElement({
          background: tierColor[status],
          borderColor: "#e8f2ff",
          glyphColor: "#00112e",
          glyphText: station.id.replace("STATION_0", ""),
          scale: 1.2,
        });
        pin.classList.add("google-station-pin");
        const stationMarker = new Marker3DInteractiveElement({
          position: { lat: point[0], lng: point[1], altitude: 4 },
          title: `${station.name} · ${station.status} · ${station.dataSource === "simulator" ? "Virtual station" : "Monitoring station"}`,
          label: station.name,
          extruded: true,
          sizePreserved: true,
          zIndex: 10,
        });
        stationMarker.append(pin);
        stationMarker.addEventListener("gmp-click", () => onSelectStation(station.id));
        map.append(stationMarker);
      });

      focus3D(map, stations, selectedStationRef.current);
      readyTimer = setTimeout(() => { if (!disposed) onStatusChange("ready"); }, 9000);
    }).catch(fail);

    return () => {
      disposed = true;
      clearTimeout(readyTimer);
      if (authWindow.gm_authFailure === fail) authWindow.gm_authFailure = previousAuthFailure;
      if (map) {
        map.removeEventListener("gmp-error", fail);
        map.removeEventListener("gmp-map-id-error", fail);
        map.stopCameraAnimation();
      }
      mapRef.current = null;
      container.replaceChildren();
    };
  }, [apiKey, mapId, onFailure, onSelectStation, onStatusChange]);

  useEffect(() => {
    const map = mapRef.current;
    if (map) focus3D(map, stations, selectedStationId);
  }, [selectedStationId, resetVersion]);

  return <div ref={containerRef} className="station-map-canvas google-3d-map-canvas" role="region" aria-label="Interactive photorealistic 3D map of Urdaneta City" tabIndex={0}/>;
}
