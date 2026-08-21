'use client';

import React from 'react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
} from 'recharts';
import { TelemetryPoint } from '@/models/telemetry';
import { format } from 'date-fns';

interface WaterLevelChartProps {
  data: TelemetryPoint[];
  advisoryThreshold?: number;
  warningThreshold?: number;
  evacuateThreshold?: number;
  height?: number;
}

export function WaterLevelChart({
  data,
  advisoryThreshold = 45,
  warningThreshold = 75,
  evacuateThreshold = 90,
  height = 260,
}: WaterLevelChartProps) {
  const chartData = data.map((d) => ({
    ...d,
    timeDisplay: format(new Date(d.timestamp), 'HH:mm'),
    fullTime: format(new Date(d.timestamp), 'MMM d, HH:mm:ss'),
  }));

  return (
    <div className="w-full bg-white rounded-xl p-4 border border-border-light shadow-card">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h4 className="text-sm font-extrabold text-typography-primary">Water Depth Progression (cm)</h4>
          <p className="text-xs text-typography-secondary">Continuous ultrasonic sensor telemetry</p>
        </div>
        <div className="flex items-center gap-3 text-xs font-semibold">
          <span className="flex items-center gap-1">
            <span className="w-3 h-0.5 bg-brand-primary inline-block"></span> Depth
          </span>
          <span className="flex items-center gap-1 text-alert-warning">
            <span className="w-3 h-0.5 bg-alert-warning inline-block"></span> Warning ({warningThreshold}cm)
          </span>
          <span className="flex items-center gap-1 text-alert-evacuate">
            <span className="w-3 h-0.5 bg-alert-evacuate inline-block"></span> Evacuate ({evacuateThreshold}cm)
          </span>
        </div>
      </div>

      <div style={{ width: '100%', height }}>
        <ResponsiveContainer>
          <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <defs>
              <linearGradient id="depthGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#0B3D91" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#0B3D91" stopOpacity={0.0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
            <XAxis
              dataKey="timeDisplay"
              stroke="#94A3B8"
              fontSize={11}
              tickLine={false}
            />
            <YAxis
              stroke="#94A3B8"
              fontSize={11}
              tickLine={false}
              domain={[0, 120]}
            />
            <Tooltip
              content={({ active, payload }) => {
                if (active && payload && payload.length) {
                  const p = payload[0].payload;
                  return (
                    <div className="bg-slate-900 text-white p-3 rounded-lg shadow-xl text-xs">
                      <p className="text-slate-400 font-medium">{p.fullTime}</p>
                      <p className="text-sm font-extrabold text-blue-300 mt-1">
                        Depth: {p.waterDepthCm} cm
                      </p>
                      <p className="text-slate-300">Rainfall: {p.rainfallMm} mm/h</p>
                      <p className="text-slate-300">Flow: {p.flowSpeedMs} m/s</p>
                    </div>
                  );
                }
                return null;
              }}
            />
            <ReferenceLine
              y={advisoryThreshold}
              stroke="#EAB308"
              strokeDasharray="4 4"
              label={{ value: 'Advisory', fill: '#EAB308', fontSize: 10, position: 'right' }}
            />
            <ReferenceLine
              y={warningThreshold}
              stroke="#F97316"
              strokeDasharray="4 4"
              label={{ value: 'Warning', fill: '#F97316', fontSize: 10, position: 'right' }}
            />
            <ReferenceLine
              y={evacuateThreshold}
              stroke="#DC2626"
              strokeDasharray="4 4"
              label={{ value: 'Evacuate', fill: '#DC2626', fontSize: 10, position: 'right' }}
            />
            <Area
              type="monotone"
              dataKey="waterDepthCm"
              stroke="#0B3D91"
              strokeWidth={2.5}
              fillOpacity={1}
              fill="url(#depthGradient)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
