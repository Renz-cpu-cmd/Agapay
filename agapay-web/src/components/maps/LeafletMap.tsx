'use client';

import React, { useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { Station } from '@/models/station';
import { SOSBeacon } from '@/models/sos';
import { ALERT_CONFIGS } from '@/constants/theme';
import { StatusBadge } from '@/components/common/StatusBadge';
import { formatWaterLevel, formatRainfall, formatBattery, formatRelativeTime } from '@/lib/formatters';

interface LeafletMapProps {
  stations: Station[];
  sosBeacons?: SOSBeacon[];
  selectedStationId?: string;
  onSelectStation?: (station: Station) => void;
  height?: string;
  center?: [number, number];
  zoom?: number;
}

// Custom DivIcon creator for River Stations
function createStationIcon(station: Station, isSelected: boolean) {
  const config = ALERT_CONFIGS[station.alertLevel] || ALERT_CONFIGS.NORMAL;
  const pulseClass = station.alertLevel === 'EVACUATE' ? 'animate-ping' : '';

  return L.divIcon({
    className: 'custom-station-marker',
    html: `
      <div style="position: relative; display: flex; flex-direction: column; align-items: center;">
        ${
          station.alertLevel === 'EVACUATE'
            ? `<div style="position: absolute; top: 0; left: 50%; transform: translateX(-50%); width: 32px; height: 32px; border-radius: 50%; background-color: rgba(220, 38, 38, 0.4);" class="${pulseClass}"></div>`
            : ''
        }
        <div style="
          width: 28px;
          height: 28px;
          border-radius: 50%;
          background-color: ${config.color};
          border: ${isSelected ? '3px solid #000' : '2px solid #fff'};
          box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
          display: flex;
          align-items: center;
          justify-content: center;
          color: white;
          font-weight: 900;
          font-size: 11px;
        ">
          ⚡
        </div>
        <div style="
          background: rgba(255,255,255,0.95);
          border: 1px solid #CBD5E1;
          border-radius: 4px;
          padding: 1px 4px;
          font-size: 10px;
          font-weight: 800;
          color: ${config.textColor};
          margin-top: 2px;
          white-space: nowrap;
          box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        ">
          ${station.waterDepthCm} cm
        </div>
      </div>
    `,
    iconSize: [40, 50],
    iconAnchor: [20, 25],
    popupAnchor: [0, -25],
  });
}

// Custom DivIcon for SOS Emergency Beacons
function createSOSIcon(sos: SOSBeacon) {
  return L.divIcon({
    className: 'custom-sos-marker',
    html: `
      <div style="position: relative; display: flex; flex-direction: column; align-items: center;">
        <div style="position: absolute; top: -4px; left: 50%; transform: translateX(-50%); width: 36px; height: 36px; border-radius: 50%; background-color: rgba(225, 29, 72, 0.4);" class="animate-ping"></div>
        <div style="
          width: 28px;
          height: 28px;
          border-radius: 50%;
          background-color: #E11D48;
          border: 2px solid #fff;
          box-shadow: 0 4px 8px rgba(225, 29, 72, 0.4);
          display: flex;
          align-items: center;
          justify-content: center;
          color: white;
          font-size: 12px;
        ">
          🚨
        </div>
        <div style="
          background: #E11D48;
          color: white;
          border-radius: 4px;
          padding: 1px 5px;
          font-size: 9px;
          font-weight: 900;
          margin-top: 2px;
          white-space: nowrap;
          letter-spacing: 0.5px;
        ">
          SOS
        </div>
      </div>
    `,
    iconSize: [40, 50],
    iconAnchor: [20, 25],
    popupAnchor: [0, -25],
  });
}

function MapViewController({ center, zoom }: { center: [number, number]; zoom: number }) {
  const map = useMap();
  useEffect(() => {
    map.setView(center, zoom);
  }, [center, zoom, map]);
  return null;
}

export function LeafletMap({
  stations,
  sosBeacons = [],
  selectedStationId,
  onSelectStation,
  height = '480px',
  center = [14.7365, 120.9582],
  zoom = 13,
}: LeafletMapProps) {
  return (
    <div style={{ height, width: '100%' }} className="rounded-xl overflow-hidden relative border border-border-light shadow-card">
      <MapContainer
        center={center}
        zoom={zoom}
        style={{ height: '100%', width: '100%' }}
        scrollWheelZoom={true}
      >
        <MapViewController center={center} zoom={zoom} />
        {/* Clean Carto Light basemap tiles */}
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
        />

        {/* Stations Markers */}
        {stations.map((st) => (
          <Marker
            key={st.id}
            position={[st.latitude, st.longitude]}
            icon={createStationIcon(st, st.id === selectedStationId)}
            eventHandlers={{
              click: () => onSelectStation?.(st),
            }}
          >
            <Popup className="custom-leaflet-popup">
              <div className="p-1 min-w-[200px]">
                <div className="flex items-center justify-between gap-2 border-b border-border-light pb-2 mb-2">
                  <div>
                    <h4 className="font-extrabold text-sm text-typography-primary leading-tight">{st.name}</h4>
                    <p className="text-[11px] text-typography-secondary">{st.barangay}</p>
                  </div>
                  <StatusBadge level={st.alertLevel} size="sm" />
                </div>

                <div className="grid grid-cols-2 gap-2 text-xs py-1">
                  <div>
                    <span className="text-typography-muted text-[10px] block">Water Level</span>
                    <strong className="text-sm font-black text-brand-primary">
                      {formatWaterLevel(st.waterDepthCm)}
                    </strong>
                  </div>
                  <div>
                    <span className="text-typography-muted text-[10px] block">Rainfall</span>
                    <strong className="text-sm font-extrabold text-typography-primary">
                      {formatRainfall(st.rainfallMm)}
                    </strong>
                  </div>
                  <div>
                    <span className="text-typography-muted text-[10px] block">Battery</span>
                    <span className="font-bold text-typography-secondary">{formatBattery(st.batteryPercent)}</span>
                  </div>
                  <div>
                    <span className="text-typography-muted text-[10px] block">Last Ping</span>
                    <span className="font-medium text-typography-secondary text-[10px]">
                      {formatRelativeTime(st.lastPing)}
                    </span>
                  </div>
                </div>

                <div className="mt-2 pt-2 border-t border-border-light text-center">
                  <a
                    href={`/stations/${st.id}`}
                    className="text-xs font-bold text-brand-primary hover:underline"
                  >
                    View Telemetry & Hydrograph &rarr;
                  </a>
                </div>
              </div>
            </Popup>
          </Marker>
        ))}

        {/* SOS Emergency Markers */}
        {sosBeacons
          .filter((b) => b.status !== 'Resolved')
          .map((sos) => (
            <Marker key={sos.id} position={[sos.latitude, sos.longitude]} icon={createSOSIcon(sos)}>
              <Popup>
                <div className="p-1 min-w-[220px]">
                  <div className="flex items-center justify-between gap-2 border-b border-border-light pb-2 mb-2">
                    <div>
                      <h4 className="font-black text-sm text-alert-evacuate flex items-center gap-1">
                        🚨 EMERGENCY SOS
                      </h4>
                      <p className="text-xs font-bold text-typography-primary">{sos.residentName}</p>
                    </div>
                    <span className="text-[10px] font-black px-2 py-0.5 rounded bg-alert-evacuateBg text-alert-evacuate">
                      {sos.status}
                    </span>
                  </div>

                  <p className="text-xs text-typography-secondary bg-surface-secondary p-2 rounded mb-2">
                    {sos.message}
                  </p>

                  <div className="text-[11px] text-typography-muted space-y-1">
                    <p>
                      <strong>Phone:</strong> {sos.phone}
                    </p>
                    <p>
                      <strong>Barangay:</strong> {sos.barangay}
                    </p>
                    <p>
                      <strong>Time:</strong> {formatRelativeTime(sos.createdAt)}
                    </p>
                    {sos.responderTeam && (
                      <p className="text-brand-primary font-bold">
                        <strong>Assigned:</strong> {sos.responderTeam}
                      </p>
                    )}
                  </div>
                </div>
              </Popup>
            </Marker>
          ))}
      </MapContainer>

      {/* Floating Tactical Legend Overlay */}
      <div className="absolute top-3 right-3 z-[1000] bg-white/95 backdrop-blur-sm p-3 rounded-xl border border-border-light shadow-md text-xs">
        <h5 className="font-extrabold text-typography-primary text-[11px] uppercase tracking-wider mb-1.5">
          Map Assets
        </h5>
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-alert-normal border border-white inline-block"></span>
            <span className="font-medium text-typography-secondary">Safe / Normal</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-alert-warning border border-white inline-block"></span>
            <span className="font-medium text-typography-secondary">Warning Level</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-alert-evacuate border border-white inline-block animate-pulse"></span>
            <span className="font-medium text-typography-secondary">Evacuate Level</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-alert-sos border border-white inline-block"></span>
            <span className="font-bold text-alert-sos">Active SOS Beacon</span>
          </div>
        </div>
      </div>
    </div>
  );
}
