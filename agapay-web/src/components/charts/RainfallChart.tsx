'use client';

import React from 'react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts';
import { TelemetryPoint } from '@/models/telemetry';
import { format } from 'date-fns';

interface RainfallChartProps {
  data: TelemetryPoint[];
  height?: number;
}

export function RainfallChart({ data, height = 200 }: RainfallChartProps) {
  const chartData = data.map((d) => ({
    ...d,
    timeDisplay: format(new Date(d.timestamp), 'HH:mm'),
    fullTime: format(new Date(d.timestamp), 'MMM d, HH:mm:ss'),
  }));

  return (
    <div className="w-full bg-white rounded-xl p-4 border border-border-light shadow-card">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h4 className="text-sm font-extrabold text-typography-primary">Precipitation & Rainfall Intensity</h4>
          <p className="text-xs text-typography-secondary">Tipping bucket precipitation rates (mm/h)</p>
        </div>
        <span className="text-xs font-bold text-sky-600 bg-sky-50 px-2 py-0.5 rounded-full border border-sky-200">
          Hourly Rainfall
        </span>
      </div>

      <div style={{ width: '100%', height }}>
        <ResponsiveContainer>
          <BarChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
            <XAxis dataKey="timeDisplay" stroke="#94A3B8" fontSize={11} tickLine={false} />
            <YAxis stroke="#94A3B8" fontSize={11} tickLine={false} />
            <Tooltip
              content={({ active, payload }) => {
                if (active && payload && payload.length) {
                  const p = payload[0].payload;
                  return (
                    <div className="bg-slate-900 text-white p-3 rounded-lg shadow-xl text-xs">
                      <p className="text-slate-400 font-medium">{p.fullTime}</p>
                      <p className="text-sm font-extrabold text-sky-300 mt-1">
                        Rainfall: {p.rainfallMm} mm/h
                      </p>
                    </div>
                  );
                }
                return null;
              }}
            />
            <Bar dataKey="rainfallMm" fill="#0284C7" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
