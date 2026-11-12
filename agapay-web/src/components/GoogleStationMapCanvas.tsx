"use client";
import { stationStatusDescription, stationMarkerTier } from "@/lib/station-map";

import { useEffect, useRef } from "react";
import { useTheme } from "@/context/ThemeContext";
import { tierColor, type Station } from "@/data/mockData";
import { loadGoogleMapLibraries } from "@/lib/google-maps";
import { cityMapCenter, cityMapZoom, stationCoordinates, type MapTileStatus } from "@/lib/station-map";

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

function focusStation(map: google.maps.Map, stations: Station[], stationId: string) {
  const station = stations.find(item => item.id === stationId);
  const point = station && stationCoordinates(station);
  map.moveCamera(point
    ? { center: { lat: point[0], lng: point[1] }, zoom: 17, tilt: 55 }
    : { center: { lat: cityMapCenter[0], lng: cityMapCenter[1] }, zoom: cityMapZoom, tilt: 42, heading: 0 });
}

export default function GoogleStationMapCanvas({
  apiKey,
  mapId,
  stations,
  selectedStationId,
  resetVersion,
  onSelectStation,
  onStatusChange,
  onFailure,
}: Props) {
  const { theme, ready } = useTheme();
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<google.maps.Map | null>(null);
  const cameraRef = useRef<google.maps.MapOptions | null>(null);
  const selectedStationRef = useRef(selectedStationId);

  useEffect(() => { selectedStationRef.current = selectedStationId; }, [selectedStationId]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || !ready) return;

    let disposed = false;
    let map: google.maps.Map | null = null;
    let markers: google.maps.marker.AdvancedMarkerElement[] = [];
    let readyTimer: ReturnType<typeof setTimeout> | undefined;
    const authWindow = window as typeof window & { gm_authFailure?: () => void };
    const previousAuthFailure = authWindow.gm_authFailure;
    const fail = () => { if (!disposed) onFailure(); };
    authWindow.gm_authFailure = fail;
    onStatusChange("loading");

    loadGoogleMapLibraries(apiKey).then(({ maps, core, marker }) => {
      if (disposed || !containerRef.current) return;
      const { Map, MapTypeControlStyle, MapTypeId, RenderingType } = maps;
      const { ColorScheme, ControlPosition, event } = core;
      const { AdvancedMarkerElement, PinElement } = marker;

      map = new Map(containerRef.current, {
        center: { lat: cityMapCenter[0], lng: cityMapCenter[1] },
        zoom: cityMapZoom,
        tilt: 42,
        heading: 0,
        mapId: mapId || Map.DEMO_MAP_ID,
        mapTypeId: MapTypeId.ROADMAP,
        renderingType: RenderingType.VECTOR,
        colorScheme: theme === "dark" ? ColorScheme.DARK : ColorScheme.LIGHT,
        backgroundColor: theme === "dark" ? "#00112e" : "#f3f6fb",
        gestureHandling: "greedy",
        headingInteractionEnabled: true,
        tiltInteractionEnabled: true,
        keyboardShortcuts: true,
        cameraControl: true,
        zoomControl: true,
        rotateControl: true,
        fullscreenControl: true,
        streetViewControl: true,
        scaleControl: true,
        mapTypeControl: true,
        mapTypeControlOptions: {
          position: ControlPosition.TOP_LEFT,
          style: MapTypeControlStyle.DROPDOWN_MENU,
          mapTypeIds: [MapTypeId.ROADMAP, MapTypeId.TERRAIN, MapTypeId.SATELLITE, MapTypeId.HYBRID],
        },
        minZoom: 3,
        maxZoom: 21,
        ...(cameraRef.current ?? {}),
      });
      mapRef.current = map;

      markers = stations.flatMap(station => {
        const point = stationCoordinates(station);
        if (!point || !map) return [];
        const status = stationMarkerTier(station);
        const pin = new PinElement({
          background: tierColor[status],
          borderColor: "#e8f2ff",
          glyphColor: "#00112e",
          glyphText: station.id.replace("STATION_0", ""),
          scale: 1.15,
        });
        pin.classList.add("google-station-pin");
        const stationMarker = new AdvancedMarkerElement({
          map,
          position: { lat: point[0], lng: point[1] },
          title: `${station.name} · ${stationStatusDescription(station)}`,
          content: pin,
          gmpClickable: true,
          zIndex: 10,
        });
        stationMarker.addEventListener("gmp-click", () => onSelectStation(station.id));
        return [stationMarker];
      });

      event.addListenerOnce(map, "tilesloaded", () => {
        if (!disposed) onStatusChange("ready");
      });
      readyTimer = setTimeout(() => {
        if (!disposed) onStatusChange("ready");
      }, 8000);
      if (!cameraRef.current) focusStation(map, stations, selectedStationRef.current);
    }).catch(fail);

    return () => {
      disposed = true;
      clearTimeout(readyTimer);
      if (authWindow.gm_authFailure === fail) authWindow.gm_authFailure = previousAuthFailure;
      markers.forEach(marker => { marker.map = null; });
      if (map && window.google?.maps) {
        cameraRef.current = { center: map.getCenter(), zoom: map.getZoom(), tilt: map.getTilt(), heading: map.getHeading(), mapTypeId: map.getMapTypeId() };
        window.google.maps.event.clearInstanceListeners(map);
      }
      mapRef.current = null;
      container.replaceChildren();
    };
  }, [ready, theme, apiKey, mapId, onFailure, onSelectStation, onStatusChange]);

  useEffect(() => {
    const map = mapRef.current;
    if (map) focusStation(map, stations, selectedStationId);
  }, [selectedStationId, resetVersion]);

  return <div ref={containerRef} className="station-map-canvas google-map-canvas" role="region" aria-label="Interactive 3D map of Urdaneta City" tabIndex={0}/>;
}
