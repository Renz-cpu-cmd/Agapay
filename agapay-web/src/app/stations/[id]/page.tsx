'use client';

import React, { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { NavigationShell } from '@/components/layout/NavigationShell';
import { useDashboard } from '@/context/DashboardContext';
import { StatusBadge } from '@/components/common/StatusBadge';
import { WaterLevelChart } from '@/components/charts/WaterLevelChart';
import { RainfallChart } from '@/components/charts/RainfallChart';
import { PredictionChart } from '@/components/charts/PredictionChart';
import { WaterGauge } from '@/components/dashboard/WaterGauge';
import { TelemetryPoint, PredictionPoint } from '@/models/telemetry';
import { stationRepository } from '@/repositories/stationRepository';
import {
  ArrowLeft,
  RefreshCw,
  Sliders,
  Radio,
  BatteryCharging,
  Wifi,
  Waves,
  Gauge,
  Calendar,
  AlertTriangle,
} from 'lucide-react';
import { formatWaterLevel, formatRainfall, formatBattery, formatRelativeTime, formatCoordinates } from '@/lib/formatters';

export default function StationDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { stations, updateStationThresholds } = useDashboard();
  const stationId = params.id as string;

  const station = stations.find((s) => s.id === stationId) || stations[0];
  const [telemetry, setTelemetry] = useState<TelemetryPoint[]>([]);
  const [predictions, setPredictions] = useState<PredictionPoint[]>([]);
  const [timeRange, setTimeRange] = useState<number>(24);
  const [isEditingThresholds, setIsEditingThresholds] = useState<boolean>(false);
  const [thresholdAdvisory, setThresholdAdvisory] = useState<number>(station?.advisoryThresholdCm || 45);
  const [thresholdWarning, setThresholdWarning] = useState<number>(station?.warningThresholdCm || 75);
  const [thresholdEvacuate, setThresholdEvacuate] = useState<number>(station?.evacuateThresholdCm || 90);

  useEffect(() => {
    if (station) {
      stationRepository.getTelemetryHistory(station.id, timeRange).then(setTelemetry);
      stationRepository.getMLPredictions(station.id).then(setPredictions);
    }
  }, [station?.id, timeRange]);

  if (!station) {
    return (
      <NavigationShell>
        <div className="p-12 text-center">
          <p className="text-sm font-bold text-typography-muted">Station not found.</p>
        </div>
      </NavigationShell>
    );
  }

  const handleSaveThresholds = async (e: React.FormEvent) => {
    e.preventDefault();
    await updateStationThresholds(station.id, {
      advisory: Number(thresholdAdvisory),
      warning: Number(thresholdWarning),
      evacuate: Number(thresholdEvacuate),
    });
    setIsEditingThresholds(false);
  };

  return (
    <NavigationShell>
      <div className="space-y-6">
        {/* Top Header & Breadcrumb */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <button
              onClick={() => router.push('/stations')}
              className="p-2 rounded-xl bg-white border border-border-light text-typography-secondary hover:text-typography-primary transition-colors"
            >
              <ArrowLeft size={18} />
            </button>
            <div>
              <div className="flex items-center gap-2.5">
                <h1 className="text-2xl font-black text-typography-primary">{station.name}</h1>
                <StatusBadge level={station.alertLevel} size="md" />
              </div>
              <p className="text-xs font-semibold text-typography-secondary mt-0.5">
                {station.barangay} · Station ID: <span className="font-mono">{station.id}</span> ·{' '}
                {formatCoordinates(station.latitude, station.longitude)}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => setIsEditingThresholds(!isEditingThresholds)}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-border-light text-typography-primary rounded-xl text-xs font-bold shadow-sm hover:bg-surface-secondary"
            >
              <Sliders size={14} />
              <span>{isEditingThresholds ? 'Cancel Config' : 'Configure Thresholds'}</span>
            </button>
          </div>
        </div>

        {/* Threshold Editor Modal / Drawer (if open) */}
        {isEditingThresholds && (
          <form
            onSubmit={handleSaveThresholds}
            className="bg-white p-5 rounded-2xl border-2 border-brand-secondary/40 shadow-xl space-y-4 animate-in fade-in"
          >
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-black text-typography-primary uppercase">
                Update Automated Alert Trigger Thresholds
              </h3>
              <span className="text-xs text-typography-muted">All values in centimeters (cm)</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-bold text-alert-advisoryText uppercase mb-1">
                  Advisory Level (cm)
                </label>
                <input
                  type="number"
                  value={thresholdAdvisory}
                  onChange={(e) => setThresholdAdvisory(Number(e.target.value))}
                  className="w-full text-xs font-bold p-2.5 rounded-xl border border-yellow-300 bg-yellow-50 focus:bg-white outline-none"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-alert-warningText uppercase mb-1">
                  Warning Level (cm)
                </label>
                <input
                  type="number"
                  value={thresholdWarning}
                  onChange={(e) => setThresholdWarning(Number(e.target.value))}
                  className="w-full text-xs font-bold p-2.5 rounded-xl border border-orange-300 bg-orange-50 focus:bg-white outline-none"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-alert-evacuateText uppercase mb-1">
                  Evacuate Level (cm)
                </label>
                <input
                  type="number"
                  value={thresholdEvacuate}
                  onChange={(e) => setThresholdEvacuate(Number(e.target.value))}
                  className="w-full text-xs font-bold p-2.5 rounded-xl border border-red-300 bg-red-50 focus:bg-white outline-none"
                  required
                />
              </div>
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setIsEditingThresholds(false)}
                className="px-4 py-2 text-xs font-bold text-typography-secondary"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-5 py-2 text-xs font-extrabold text-white bg-brand-primary hover:bg-brand-primaryDark rounded-xl shadow-md"
              >
                Save Threshold Changes
              </button>
            </div>
          </form>
        )}

        {/* Telemetry HUD (Gauge & Hardware Status Grid) */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Gauge Card */}
          <div className="lg:col-span-4 bg-white p-5 rounded-2xl border border-border-light shadow-card flex flex-col items-center justify-center">
            <h4 className="text-xs font-bold text-typography-secondary uppercase mb-2">Live Water Level Gauge</h4>
            <WaterGauge
              depthCm={station.waterDepthCm}
              maxDepthCm={station.maxThresholdCm}
              alertLevel={station.alertLevel}
              size={220}
            />

            <div className="w-full grid grid-cols-3 gap-2 mt-4 pt-3 border-t border-border-light text-center text-xs">
              <div className="p-2 rounded-lg bg-yellow-50 text-yellow-800 border border-yellow-200">
                <span className="text-[10px] font-bold block">Advisory</span>
                <strong>≥ {station.advisoryThresholdCm} cm</strong>
              </div>
              <div className="p-2 rounded-lg bg-orange-50 text-orange-800 border border-orange-200">
                <span className="text-[10px] font-bold block">Warning</span>
                <strong>≥ {station.warningThresholdCm} cm</strong>
              </div>
              <div className="p-2 rounded-lg bg-red-50 text-red-800 border border-red-200">
                <span className="text-[10px] font-bold block">Evacuate</span>
                <strong>≥ {station.evacuateThresholdCm} cm</strong>
              </div>
            </div>
          </div>

          {/* Sensor Array Metrics */}
          <div className="lg:col-span-8 grid grid-cols-2 sm:grid-cols-3 gap-4">
            <div className="bg-white p-4 rounded-xl border border-border-light shadow-card">
              <span className="text-xs font-bold text-typography-secondary uppercase block">Precipitation Rate</span>
              <h3 className="text-2xl font-black text-typography-primary mt-1">
                {formatRainfall(station.rainfallMm)}
              </h3>
              <p className="text-[11px] text-typography-muted mt-1">Tipping bucket sensor</p>
            </div>

            <div className="bg-white p-4 rounded-xl border border-border-light shadow-card">
              <span className="text-xs font-bold text-typography-secondary uppercase block">Surface Velocity</span>
              <h3 className="text-2xl font-black text-typography-primary mt-1">
                {station.flowSpeedMs.toFixed(2)} <span className="text-xs font-bold">m/s</span>
              </h3>
              <p className="text-[11px] text-typography-muted mt-1">Doppler flow sensor</p>
            </div>

            <div className="bg-white p-4 rounded-xl border border-border-light shadow-card">
              <span className="text-xs font-bold text-typography-secondary uppercase block">Battery Level</span>
              <h3 className="text-2xl font-black text-typography-primary mt-1">
                {formatBattery(station.batteryPercent)}
              </h3>
              <p className="text-[11px] text-emerald-600 font-bold mt-1">
                {station.solarCharging ? 'Solar charging active' : 'Discharging'}
              </p>
            </div>

            <div className="bg-white p-4 rounded-xl border border-border-light shadow-card">
              <span className="text-xs font-bold text-typography-secondary uppercase block">MQTT Telemetry</span>
              <h3 className="text-lg font-black text-emerald-600 mt-1 flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                Connected
              </h3>
              <p className="text-[11px] text-typography-muted mt-1">Broker latency: ~38ms</p>
            </div>

            <div className="bg-white p-4 rounded-xl border border-border-light shadow-card">
              <span className="text-xs font-bold text-typography-secondary uppercase block">Signal RSSI</span>
              <h3 className="text-2xl font-black text-typography-primary mt-1">{station.rssi} dBm</h3>
              <p className="text-[11px] text-typography-muted mt-1">4G LTE Industrial Link</p>
            </div>

            <div className="bg-white p-4 rounded-xl border border-border-light shadow-card">
              <span className="text-xs font-bold text-typography-secondary uppercase block">Last Heartbeat</span>
              <h3 className="text-sm font-black text-typography-primary mt-1">
                {formatRelativeTime(station.lastPing)}
              </h3>
              <p className="text-[11px] text-typography-muted mt-1">10s telemetry interval</p>
            </div>
          </div>
        </div>

        {/* Timeframe Selector & Charts */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-extrabold text-typography-primary">Historical Telemetry Hydrographs</h3>
            <div className="flex items-center gap-2 bg-white p-1 rounded-xl border border-border-light text-xs font-bold">
              {[
                { label: '24 Hours', hours: 24 },
                { label: '7 Days', hours: 168 },
                { label: '30 Days', hours: 720 },
              ].map((t) => (
                <button
                  key={t.hours}
                  onClick={() => setTimeRange(t.hours)}
                  className={`px-3 py-1.5 rounded-lg transition-all ${
                    timeRange === t.hours
                      ? 'bg-brand-primary text-white shadow-sm'
                      : 'text-typography-secondary hover:text-typography-primary'
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <WaterLevelChart
              data={telemetry}
              advisoryThreshold={station.advisoryThresholdCm}
              warningThreshold={station.warningThresholdCm}
              evacuateThreshold={station.evacuateThresholdCm}
              height={260}
            />
            <RainfallChart data={telemetry} height={260} />
          </div>
        </div>

        {/* AI / ML Predictive Model Section */}
        <PredictionChart
          predictions={predictions}
          currentDepth={station.waterDepthCm}
          evacuateThreshold={station.evacuateThresholdCm}
        />

        {/* Historical Telemetry Logs Table */}
        <div className="bg-white rounded-2xl border border-border-light shadow-card overflow-hidden">
          <div className="p-4 border-b border-border-light">
            <h4 className="text-sm font-black text-typography-primary">Recent Sensor Telemetry Log</h4>
            <p className="text-xs text-typography-secondary">Recorded readings received from ESP32 station</p>
          </div>
          <div className="overflow-x-auto max-h-72">
            <table className="w-full text-left text-xs">
              <thead className="bg-surface-secondary text-typography-secondary font-bold uppercase text-[10px] sticky top-0">
                <tr>
                  <th className="py-2.5 px-4">Timestamp</th>
                  <th className="py-2.5 px-4">Water Depth</th>
                  <th className="py-2.5 px-4">Rainfall</th>
                  <th className="py-2.5 px-4">Flow Velocity</th>
                  <th className="py-2.5 px-4">Battery</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-light font-semibold">
                {telemetry.slice(0, 10).map((pt, i) => (
                  <tr key={i} className="hover:bg-surface-secondary/40">
                    <td className="py-2.5 px-4 text-typography-secondary">{pt.timestamp}</td>
                    <td className="py-2.5 px-4 font-black text-brand-primary">{pt.waterDepthCm} cm</td>
                    <td className="py-2.5 px-4 font-bold">{pt.rainfallMm} mm/h</td>
                    <td className="py-2.5 px-4">{pt.flowSpeedMs} m/s</td>
                    <td className="py-2.5 px-4">{pt.batteryPercent}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </NavigationShell>
  );
}
