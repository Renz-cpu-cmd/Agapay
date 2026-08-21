'use client';

import React, { useState, useEffect } from 'react';
import { NavigationShell } from '@/components/layout/NavigationShell';
import { useDashboard } from '@/context/DashboardContext';
import { WaterLevelChart } from '@/components/charts/WaterLevelChart';
import { RainfallChart } from '@/components/charts/RainfallChart';
import { TelemetryPoint } from '@/models/telemetry';
import { stationRepository } from '@/repositories/stationRepository';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts';
import { LineChart as ChartIcon, TrendingUp, Waves, Brain, Activity } from 'lucide-react';
import { formatWaterLevel, formatRainfall } from '@/lib/formatters';

export default function AnalyticsPage() {
  const { stations } = useDashboard();
  const [timeRange, setTimeRange] = useState<number>(24);
  const [primaryTelemetry, setPrimaryTelemetry] = useState<TelemetryPoint[]>([]);
  const [secondaryTelemetry, setSecondaryTelemetry] = useState<TelemetryPoint[]>([]);

  useEffect(() => {
    if (stations.length >= 2) {
      stationRepository.getTelemetryHistory(stations[0].id, timeRange).then(setPrimaryTelemetry);
      stationRepository.getTelemetryHistory(stations[1].id, timeRange).then(setSecondaryTelemetry);
    }
  }, [stations, timeRange]);

  // Combined Multi-Station Comparison Data
  const comparisonData = primaryTelemetry.map((pt, i) => ({
    timeDisplay: pt.timestamp.split('T')[1].slice(0, 5),
    sanNicolas: pt.waterDepthCm,
    poblacion: secondaryTelemetry[i]?.waterDepthCm || pt.waterDepthCm - 15,
  }));

  return (
    <NavigationShell>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-black text-typography-primary tracking-tight">
              Historical Flood Telemetry & Analytics
            </h1>
            <p className="text-xs font-semibold text-typography-secondary mt-0.5">
              Multi-station correlation, catchment run-off trends, and hydrodynamic predictive performance
            </p>
          </div>

          <div className="flex items-center gap-2 bg-white p-1 rounded-xl border border-border-light text-xs font-bold shadow-sm">
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

        {/* Statistical Summary Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-white p-4 rounded-xl border border-border-light shadow-card">
            <span className="text-xs font-bold text-typography-secondary uppercase block">Peak Water Level</span>
            <h3 className="text-2xl font-black text-alert-evacuate mt-1">102.4 cm</h3>
            <p className="text-[11px] text-typography-muted mt-1">San Nicolas Bridge (T-2h ago)</p>
          </div>

          <div className="bg-white p-4 rounded-xl border border-border-light shadow-card">
            <span className="text-xs font-bold text-typography-secondary uppercase block">Cumulative Rainfall</span>
            <h3 className="text-2xl font-black text-sky-600 mt-1">42.8 mm</h3>
            <p className="text-[11px] text-typography-muted mt-1">Precipitation across sector</p>
          </div>

          <div className="bg-white p-4 rounded-xl border border-border-light shadow-card">
            <span className="text-xs font-bold text-typography-secondary uppercase block">AI Forecast Accuracy</span>
            <h3 className="text-2xl font-black text-brand-primary mt-1">94.2%</h3>
            <p className="text-[11px] text-typography-muted mt-1">LSTM neural model benchmark</p>
          </div>

          <div className="bg-white p-4 rounded-xl border border-border-light shadow-card">
            <span className="text-xs font-bold text-typography-secondary uppercase block">River Surface Runoff</span>
            <h3 className="text-2xl font-black text-typography-primary mt-1">2.10 m/s</h3>
            <p className="text-[11px] text-typography-muted mt-1">Current maximum velocity</p>
          </div>
        </div>

        {/* Multi-Station Comparative Hydrograph */}
        <div className="bg-white rounded-2xl p-5 border border-border-light shadow-card space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-black text-typography-primary uppercase tracking-wider">
                Multi-Station River Depth Comparison (cm)
              </h3>
              <p className="text-xs text-typography-secondary">
                Correlating upstream vs downstream hydrodynamic level trends
              </p>
            </div>
            <div className="flex items-center gap-4 text-xs font-bold">
              <span className="flex items-center gap-1.5 text-brand-primary">
                <span className="w-3 h-0.5 bg-brand-primary inline-block"></span> Brgy. San Nicolas
              </span>
              <span className="flex items-center gap-1.5 text-brand-secondary">
                <span className="w-3 h-0.5 bg-brand-secondary inline-block"></span> Brgy. Poblacion
              </span>
            </div>
          </div>

          <div className="w-full h-72">
            <ResponsiveContainer>
              <LineChart data={comparisonData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
                <XAxis dataKey="timeDisplay" stroke="#94A3B8" fontSize={11} tickLine={false} />
                <YAxis stroke="#94A3B8" fontSize={11} tickLine={false} domain={[0, 120]} />
                <Tooltip
                  content={({ active, payload }) => {
                    if (active && payload && payload.length) {
                      return (
                        <div className="bg-slate-900 text-white p-3 rounded-lg shadow-xl text-xs space-y-1">
                          <p className="text-slate-400 font-medium">{payload[0].payload.timeDisplay}</p>
                          <p className="text-blue-300 font-extrabold">
                            San Nicolas: {payload[0].value} cm
                          </p>
                          <p className="text-sky-300 font-extrabold">
                            Poblacion: {payload[1]?.value} cm
                          </p>
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="sanNicolas"
                  stroke="#0B3D91"
                  strokeWidth={2.5}
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="poblacion"
                  stroke="#1976D2"
                  strokeWidth={2.5}
                  strokeDasharray="4 4"
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Detailed Rainfall & Single Station Hydrograph Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <WaterLevelChart data={primaryTelemetry} height={250} />
          <RainfallChart data={primaryTelemetry} height={250} />
        </div>
      </div>
    </NavigationShell>
  );
}
