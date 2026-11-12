"use client";

import { useEffect, useRef } from "react";
import { useTheme } from "@/context/ThemeContext";
import { loadGoogleMapLibraries } from "@/lib/google-maps";

type Props = {
  apiKey: string;
  mapId: string;
  latitude: number;
  longitude: number;
  label: string;
};

export default function GoogleSosLocationMap({ apiKey, mapId, latitude, longitude, label }: Props) {
  const { theme, ready } = useTheme();
  const containerRef = useRef<HTMLDivElement>(null);
  const cameraRef = useRef<{ latitude: number; longitude: number; options: google.maps.MapOptions } | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || !apiKey || !ready) return;

    let disposed = false;
    let map: google.maps.Map | null = null;
    let locationMarker: google.maps.marker.AdvancedMarkerElement | null = null;

    loadGoogleMapLibraries(apiKey).then(({ maps, core, marker }) => {
      if (disposed || !containerRef.current) return;
      const point = { lat: latitude, lng: longitude };
      map = new maps.Map(containerRef.current, {
        center: point,
        zoom: 17,
        mapId: mapId || maps.Map.DEMO_MAP_ID,
        colorScheme: theme === "dark" ? core.ColorScheme.DARK : core.ColorScheme.LIGHT,
        renderingType: maps.RenderingType.VECTOR,
        backgroundColor: theme === "dark" ? "#00112e" : "#f3f6fb",
        gestureHandling: "greedy",
        mapTypeControl: true,
        streetViewControl: true,
        fullscreenControl: true,
        cameraControl: true,
        zoomControl: true,
        ...(cameraRef.current?.latitude === latitude && cameraRef.current.longitude === longitude ? cameraRef.current.options : {}),
      });
      const pin = new marker.PinElement({
        background: "#ef4444",
        borderColor: "#ffffff",
        glyphColor: "#ffffff",
        scale: 1.2,
      });
      locationMarker = new marker.AdvancedMarkerElement({
        map,
        position: point,
        title: label,
        content: pin,
        zIndex: 10,
      });
    }).catch(() => {
      if (!disposed) container.textContent = "Google Maps could not load. Use the external map link below.";
    });

    return () => {
      disposed = true;
      if (locationMarker) locationMarker.map = null;
      if (map && window.google?.maps) {
        cameraRef.current = { latitude, longitude, options: { center: map.getCenter(), zoom: map.getZoom(), tilt: map.getTilt(), heading: map.getHeading(), mapTypeId: map.getMapTypeId() } };
        window.google.maps.event.clearInstanceListeners(map);
      }
      container.replaceChildren();
    };
  }, [ready, theme, apiKey, mapId, latitude, longitude, label]);

  if (!apiKey) {
    return <div className="station-map-loading h-48" role="status">Google Maps is not configured for this deployment.</div>;
  }

  return <div ref={containerRef} className="google-sos-location-map w-full h-48 rounded border border-slate-700" role="region" aria-label={label} tabIndex={0}/>;
}
