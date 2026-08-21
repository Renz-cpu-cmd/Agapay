'use client';

import React from 'react';
import { NavigationShell } from '@/components/layout/NavigationShell';
import { useDashboard } from '@/context/DashboardContext';
import {
  Activity,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Cpu,
  Wifi,
  BatteryCharging,
  Radio,
  Server,
  Zap,
} from 'lucide-react';
import { formatRelativeTime, formatBattery } from '@/lib/formatters';

export default function SystemHealthPage() {
  const { stations } = useDashboard();

  const onlineStations = stations.filter((s) => s.status === 'Online');
  const offlineStations = stations.filter((s) => s.status === 'Offline');
  const maintenanceStations = stations.filter((s) => s.status === 'Maintenance');
  const avgBattery = Math.round(
    stations.reduce((acc, s) => acc + s.batteryPercent, 0) / (stations.length || 1)
  );

  return (
    <NavigationShell>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-black text-typography-primary tracking-tight">
              Sensor Station Fleet Health & Telemetry Diagnostics
            </h1>
            <p className="text-xs font-semibold text-typography-secondary mt-0.5">
              Live hardware diagnostics for ESP32 microcontroller telemetry, MQTT broker link, and power arrays
            </p>
          </div>
        </div>

        {/* Fleet Status Summary Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-white p-4 rounded-xl border border-border-light shadow-card">
            <span className="text-xs font-bold text-typography-secondary uppercase block">Online Stations</span>
            <div className="flex items-center justify-between mt-1">
              <h3 className="text-2xl font-black text-emerald-600">
                {onlineStations.length} / {stations.length}
              </h3>
              <div className="p-2 rounded-lg bg-emerald-50 text-emerald-600">
                <CheckCircle2 size={20} />
              </div>
            </div>
            <p className="text-[11px] text-typography-muted mt-1">Transmitting continuous sensor telemetry</p>
          </div>

          <div className="bg-white p-4 rounded-xl border border-border-light shadow-card">
            <span className="text-xs font-bold text-typography-secondary uppercase block">Offline Stations</span>
            <div className="flex items-center justify-between mt-1">
              <h3 className="text-2xl font-black text-rose-600">{offlineStations.length}</h3>
              <div className="p-2 rounded-lg bg-rose-50 text-rose-600">
                <XCircle size={20} />
              </div>
            </div>
            <p className="text-[11px] text-typography-muted mt-1">No heartbeat in &gt;15 minutes</p>
          </div>

          <div className="bg-white p-4 rounded-xl border border-border-light shadow-card">
            <span className="text-xs font-bold text-typography-secondary uppercase block">Maintenance Stations</span>
            <div className="flex items-center justify-between mt-1">
              <h3 className="text-2xl font-black text-amber-600">{maintenanceStations.length}</h3>
              <div className="p-2 rounded-lg bg-amber-50 text-amber-600">
                <AlertTriangle size={20} />
              </div>
            </div>
            <p className="text-[11px] text-typography-muted mt-1">Scheduled sensor calibration</p>
          </div>

          <div className="bg-white p-4 rounded-xl border border-border-light shadow-card">
            <span className="text-xs font-bold text-typography-secondary uppercase block">Fleet Battery Health</span>
            <div className="flex items-center justify-between mt-1">
              <h3 className="text-2xl font-black text-brand-primary">{avgBattery}%</h3>
              <div className="p-2 rounded-lg bg-blue-50 text-brand-primary">
                <BatteryCharging size={20} />
              </div>
            </div>
            <p className="text-[11px] text-typography-muted mt-1">Solar harvesting operational</p>
          </div>
        </div>

        {/* Server & MQTT Broker Status Card */}
        <div className="bg-white rounded-2xl p-5 border border-border-light shadow-card">
          <h3 className="text-sm font-black text-typography-primary uppercase tracking-wider mb-3">
            Core Disaster Infrastructure Health
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-3.5 rounded-xl bg-surface-secondary border border-border-light">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Server size={18} className="text-brand-primary" />
                  <span className="text-xs font-black text-typography-primary">MQTT Telemetry Broker</span>
                </div>
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
              </div>
              <p className="text-xs text-typography-secondary mt-2">
                Status: <strong className="text-emerald-700">Healthy (2,410 msg/min)</strong>
              </p>
              <p className="text-[10px] text-typography-muted">Broker port: 8883 (TLS 1.3 MQTTS)</p>
            </div>

            <div className="p-3.5 rounded-xl bg-surface-secondary border border-border-light">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Cpu size={18} className="text-brand-primary" />
                  <span className="text-xs font-black text-typography-primary">FastAPI Ingestion Node</span>
                </div>
                <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
              </div>
              <p className="text-xs text-typography-secondary mt-2">
                Latency: <strong className="text-typography-primary">~24 ms</strong> · CPU: <strong>14%</strong>
              </p>
              <p className="text-[10px] text-typography-muted">PostgreSQL connection pool: 12/50</p>
            </div>

            <div className="p-3.5 rounded-xl bg-surface-secondary border border-border-light">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Radio size={18} className="text-brand-primary" />
                  <span className="text-xs font-black text-typography-primary">Citizen FCM Broadcast Gateway</span>
                </div>
                <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
              </div>
              <p className="text-xs text-typography-secondary mt-2">
                Subscribed Citizens: <strong className="text-typography-primary">18,420 Devices</strong>
              </p>
              <p className="text-[10px] text-typography-muted">Average push delivery: 1.4 seconds</p>
            </div>
          </div>
        </div>

        {/* Station Hardware Diagnostics Table */}
        <div className="bg-white rounded-2xl border border-border-light shadow-card overflow-hidden">
          <div className="p-4 border-b border-border-light">
            <h4 className="text-sm font-black text-typography-primary">ESP32 Station Hardware Telemetry Matrix</h4>
            <p className="text-xs text-typography-secondary">Detailed sensor probe diagnostics and power metrics</p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-semibold">
              <thead className="bg-surface-secondary text-typography-secondary text-[10px] uppercase font-bold">
                <tr>
                  <th className="py-3 px-4">Station ID & Name</th>
                  <th className="py-3 px-4">Firmware</th>
                  <th className="py-3 px-4">Last Heartbeat</th>
                  <th className="py-3 px-4">Power / Solar</th>
                  <th className="py-3 px-4">Ultrasonic Probe</th>
                  <th className="py-3 px-4">Rain Gauge</th>
                  <th className="py-3 px-4">Signal RSSI</th>
                  <th className="py-3 px-4 text-right">Node Health</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-light">
                {stations.map((st) => {
                  const isOnline = st.status === 'Online';
                  return (
                    <tr key={st.id} className="hover:bg-surface-secondary/40">
                      <td className="py-3.5 px-4">
                        <strong className="text-typography-primary block">{st.name}</strong>
                        <span className="text-[10px] font-mono text-typography-muted">{st.id}</span>
                      </td>

                      <td className="py-3.5 px-4 font-mono text-typography-secondary">{st.firmwareVersion}</td>

                      <td className="py-3.5 px-4 text-typography-secondary">{formatRelativeTime(st.lastPing)}</td>

                      <td className="py-3.5 px-4">
                        <div className="flex items-center gap-1.5">
                          <span
                            className={`w-2 h-2 rounded-full ${
                              st.batteryPercent > 80 ? 'bg-emerald-500' : 'bg-amber-500'
                            }`}
                          ></span>
                          <span className="font-bold">{st.batteryPercent}%</span>
                        </div>
                        <span className="text-[10px] text-typography-muted block">
                          {st.solarCharging ? 'Solar Active' : 'No Charge'}
                        </span>
                      </td>

                      <td className="py-3.5 px-4">
                        <span className="text-emerald-700 font-bold flex items-center gap-1">
                          <CheckCircle2 size={12} /> Operational
                        </span>
                        <span className="text-[10px] text-typography-muted block">{st.waterDepthCm} cm depth</span>
                      </td>

                      <td className="py-3.5 px-4">
                        <span className="text-emerald-700 font-bold flex items-center gap-1">
                          <CheckCircle2 size={12} /> Operational
                        </span>
                        <span className="text-[10px] text-typography-muted block">{st.rainfallMm} mm/h</span>
                      </td>

                      <td className="py-3.5 px-4 font-mono text-typography-secondary">{st.rssi} dBm</td>

                      <td className="py-3.5 px-4 text-right">
                        <span
                          className={`inline-flex items-center px-2.5 py-1 rounded-full text-[10px] font-black ${
                            isOnline
                              ? 'bg-emerald-100 text-emerald-800'
                              : st.status === 'Maintenance'
                              ? 'bg-amber-100 text-amber-800'
                              : 'bg-rose-100 text-rose-800'
                          }`}
                        >
                          {st.status}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </NavigationShell>
  );
}
