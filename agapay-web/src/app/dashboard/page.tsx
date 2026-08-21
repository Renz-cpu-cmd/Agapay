'use client';

import React, { useState, useEffect } from 'react';
import { NavigationShell } from '@/components/layout/NavigationShell';
import { useDashboard } from '@/context/DashboardContext';
import { MetricCard } from '@/components/common/MetricCard';
import { StatusBadge } from '@/components/common/StatusBadge';
import { LeafletMapWrapper } from '@/components/maps/LeafletMapWrapper';
import { WaterLevelChart } from '@/components/charts/WaterLevelChart';
import { Station } from '@/models/station';
import { TelemetryPoint } from '@/models/telemetry';
import { stationRepository } from '@/repositories/stationRepository';
import {
  BellRing,
  AlertTriangle,
  Waves,
  Siren,
  ArrowUpRight,
  TrendingUp,
  TrendingDown,
  Minus,
  RefreshCw,
  ExternalLink,
} from 'lucide-react';
import { formatWaterLevel, formatRelativeTime, formatRainfall } from '@/lib/formatters';
import Link from 'next/link';

export default function DashboardPage() {
  const {
    stations,
    alerts,
    sosBeacons,
    metrics,
    selectedBarangay,
    resolveAlert,
    refreshData,
  } = useDashboard();

  const [selectedStation, setSelectedStation] = useState<Station | null>(null);
  const [telemetryHistory, setTelemetryHistory] = useState<TelemetryPoint[]>([]);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Filter stations based on top-level jurisdiction selection
  const filteredStations =
    selectedBarangay === 'All Barangays'
      ? stations
      : stations.filter((s) => s.barangay === selectedBarangay);

  const activeStation = selectedStation || filteredStations[0] || stations[0];

  useEffect(() => {
    if (activeStation) {
      stationRepository.getTelemetryHistory(activeStation.id, 24).then(setTelemetryHistory);
    }
  }, [activeStation?.id]);

  const handleManualRefresh = async () => {
    setIsRefreshing(true);
    await refreshData();
    if (activeStation) {
      const history = await stationRepository.getTelemetryHistory(activeStation.id, 24);
      setTelemetryHistory(history);
    }
    setTimeout(() => setIsRefreshing(false), 400);
  };

  // Sort active alerts by severity: EVACUATE > WARNING > ADVISORY > NORMAL
  const severityRank: Record<string, number> = {
    EVACUATE: 4,
    WARNING: 3,
    ADVISORY: 2,
    NORMAL: 1,
  };

  const sortedAlerts = [...alerts]
    .filter((a) => a.status !== 'Resolved')
    .sort((a, b) => (severityRank[b.severity] || 0) - (severityRank[a.severity] || 0));

  return (
    <NavigationShell>
      <div className="space-y-6">
        {/* Page Title & Status Bar */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-black text-typography-primary tracking-tight">
              Disaster Operations Command Center
            </h1>
            <p className="text-xs font-semibold text-typography-secondary mt-0.5">
              Live river telemetry, automated early-warning thresholds, and resident rescue beacons
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={handleManualRefresh}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-surface-secondary text-typography-secondary hover:text-typography-primary border border-border-light rounded-xl text-xs font-bold shadow-sm transition-all"
            >
              <RefreshCw size={14} className={isRefreshing ? 'animate-spin' : ''} />
              <span>Refresh Telemetry</span>
            </button>
            <Link
              href="/sos"
              className="flex items-center gap-1.5 px-3.5 py-1.5 bg-alert-sos hover:bg-rose-700 text-white rounded-xl text-xs font-black shadow-md transition-all animate-pulse"
            >
              <Siren size={14} />
              <span>SOS Rescue Desk ({metrics.activeSOSCount})</span>
            </Link>
          </div>
        </div>

        {/* 4 Primary Metric Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCard
            title="Active Flood Alerts"
            value={metrics.activeAlertsCount}
            subtitle={`${sortedAlerts.filter((a) => a.severity === 'EVACUATE').length} Critical Evacuation Order`}
            icon={<BellRing size={22} />}
            accentColor="#F97316"
            trend={{
              value: `${sortedAlerts.length} total active bulletins`,
              isNegative: metrics.activeAlertsCount > 0,
            }}
          />

          <MetricCard
            title="Critical Stations"
            value={metrics.criticalStationsCount}
            subtitle="Warning or Evacuation tier"
            icon={<AlertTriangle size={22} />}
            accentColor="#DC2626"
            trend={{
              value: `${filteredStations.length} reporting online`,
              isNegative: metrics.criticalStationsCount > 0,
            }}
          />

          <MetricCard
            title="Average Water Level"
            value={`${metrics.averageWaterLevelCm} cm`}
            subtitle="Across monitoring stations"
            icon={<Waves size={22} />}
            accentColor="#0B3D91"
            trend={{
              value: 'Peak: 102.4 cm (San Nicolas Bridge)',
              isPositive: metrics.averageWaterLevelCm < 60,
            }}
          />

          <MetricCard
            title="Active SOS Beacons"
            value={metrics.activeSOSCount}
            subtitle="Residents awaiting dispatch"
            icon={<Siren size={22} />}
            accentColor="#E11D48"
            trend={{
              value: `${sosBeacons.filter((b) => b.status === 'EnRoute').length} Rescue boats en route`,
              isNegative: metrics.activeSOSCount > 0,
            }}
          />
        </div>

        {/* Main Grid: GIS Map (Left 7 cols) & Active Alerts / Queue (Right 5 cols) */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Live GIS Flood Map */}
          <div className="lg:col-span-7 flex flex-col space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-extrabold text-typography-primary flex items-center gap-2">
                  <span>Live Hydrodynamic Flood Map</span>
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                </h3>
                <p className="text-xs text-typography-secondary">
                  Click any sensor marker to inspect live depth, battery, and hydrographs
                </p>
              </div>
              <Link
                href="/stations"
                className="text-xs font-bold text-brand-primary hover:underline flex items-center gap-1"
              >
                <span>Full Directory</span>
                <ExternalLink size={12} />
              </Link>
            </div>

            <LeafletMapWrapper
              stations={filteredStations}
              sosBeacons={sosBeacons}
              selectedStationId={activeStation?.id}
              onSelectStation={(st) => setSelectedStation(st)}
              height="440px"
            />
          </div>

          {/* Right Panel: Priority Alerts Queue */}
          <div className="lg:col-span-5 flex flex-col space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-extrabold text-typography-primary">Priority Emergency Alerts</h3>
                <p className="text-xs text-typography-secondary">Sorted by highest severity first</p>
              </div>
              <Link
                href="/alerts"
                className="text-xs font-bold text-brand-primary hover:underline flex items-center gap-1"
              >
                <span>Alert Manager</span>
                <ArrowUpRight size={14} />
              </Link>
            </div>

            <div className="bg-white rounded-xl border border-border-light p-4 shadow-card flex-1 max-h-[440px] overflow-y-auto space-y-3">
              {sortedAlerts.length === 0 ? (
                <div className="py-12 text-center text-typography-muted text-xs">
                  No active emergency alerts in this jurisdiction.
                </div>
              ) : (
                sortedAlerts.map((alert) => {
                  const isEvacuate = alert.severity === 'EVACUATE';
                  return (
                    <div
                      key={alert.id}
                      className={`p-3.5 rounded-xl border transition-all ${
                        isEvacuate
                          ? 'bg-alert-evacuateBg/40 border-alert-evacuate/50 shadow-sm'
                          : 'bg-surface-secondary border-border-light'
                      }`}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex items-center gap-2">
                          <StatusBadge level={alert.severity} size="sm" />
                          <span className="text-xs font-extrabold text-typography-primary">
                            {alert.barangay}
                          </span>
                        </div>
                        <span className="text-[10px] font-bold text-typography-muted">
                          {formatRelativeTime(alert.createdAt)}
                        </span>
                      </div>

                      <p className="text-xs font-bold text-typography-primary mt-2">
                        {alert.stationName} · Depth: {alert.waterDepthCm} cm
                      </p>
                      <p className="text-xs text-typography-secondary mt-0.5 leading-relaxed">
                        {alert.message}
                      </p>

                      <div className="mt-2.5 pt-2 border-t border-border-light/60 flex items-center justify-between">
                        <span className="text-[11px] font-bold text-typography-muted">
                          Rain: {formatRainfall(alert.rainfallMm)}
                        </span>
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => resolveAlert(alert.id)}
                            className="px-2.5 py-1 text-[11px] font-bold bg-white hover:bg-slate-50 border border-border-light rounded-lg text-typography-primary transition-colors"
                          >
                            Mark Resolved
                          </button>
                          <Link
                            href={`/stations/${alert.stationId}`}
                            className="px-2.5 py-1 text-[11px] font-extrabold bg-brand-primary text-white hover:bg-brand-primaryDark rounded-lg transition-colors"
                          >
                            Details &rarr;
                          </Link>
                        </div>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>

        {/* Bottom Section: Active Station Hydrograph & Telemetry Breakdown */}
        {activeStation && (
          <div className="bg-white rounded-2xl p-5 border border-border-light shadow-card space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-border-light">
              <div>
                <div className="flex items-center gap-2.5">
                  <h3 className="text-lg font-black text-typography-primary">{activeStation.name}</h3>
                  <StatusBadge level={activeStation.alertLevel} size="sm" />
                </div>
                <p className="text-xs text-typography-secondary">
                  {activeStation.barangay} · Station ID: {activeStation.id} · Firmware:{' '}
                  {activeStation.firmwareVersion}
                </p>
              </div>

              {/* Station Quick Metrics */}
              <div className="flex items-center gap-4 text-xs">
                <div className="bg-surface-secondary px-3 py-1.5 rounded-lg border border-border-light">
                  <span className="text-typography-muted text-[10px] block">Water Depth</span>
                  <span className="font-black text-sm text-brand-primary">
                    {formatWaterLevel(activeStation.waterDepthCm)}
                  </span>
                </div>
                <div className="bg-surface-secondary px-3 py-1.5 rounded-lg border border-border-light">
                  <span className="text-typography-muted text-[10px] block">Trend</span>
                  <span className="font-extrabold text-xs flex items-center gap-1 text-typography-primary">
                    {activeStation.trend === 'rising' ? (
                      <TrendingUp size={14} className="text-alert-warning" />
                    ) : activeStation.trend === 'falling' ? (
                      <TrendingDown size={14} className="text-alert-normal" />
                    ) : (
                      <Minus size={14} className="text-typography-muted" />
                    )}
                    <span className="capitalize">{activeStation.trend}</span>
                  </span>
                </div>
                <div className="bg-surface-secondary px-3 py-1.5 rounded-lg border border-border-light">
                  <span className="text-typography-muted text-[10px] block">Battery</span>
                  <span className="font-extrabold text-xs text-typography-primary">
                    {activeStation.batteryPercent}%
                  </span>
                </div>
              </div>
            </div>

            {/* Recharts Hydrograph */}
            <WaterLevelChart
              data={telemetryHistory}
              advisoryThreshold={activeStation.advisoryThresholdCm}
              warningThreshold={activeStation.warningThresholdCm}
              evacuateThreshold={activeStation.evacuateThresholdCm}
              height={220}
            />
          </div>
        )}
      </div>
    </NavigationShell>
  );
}
