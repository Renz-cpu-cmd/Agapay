'use client';

import React from 'react';
import { AlertLevel, ALERT_CONFIGS } from '@/constants/theme';

interface WaterGaugeProps {
  depthCm: number;
  maxDepthCm?: number;
  advisoryThreshold?: number;
  warningThreshold?: number;
  evacuateThreshold?: number;
  alertLevel: AlertLevel;
  size?: number;
}

export function WaterGauge({
  depthCm,
  maxDepthCm = 120,
  alertLevel,
  size = 180,
}: WaterGaugeProps) {
  const percentage = Math.min(100, Math.max(0, (depthCm / maxDepthCm) * 100));
  const config = ALERT_CONFIGS[alertLevel] || ALERT_CONFIGS.NORMAL;

  // Arc calculation for SVG gauge (from 135deg to 405deg = 270deg span)
  const radius = (size - 24) / 2;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (percentage / 100) * (circumference * 0.75);

  return (
    <div className="flex flex-col items-center justify-center p-3">
      <div className="relative flex items-center justify-center" style={{ width: size, height: size * 0.85 }}>
        <svg width={size} height={size} className="transform -rotate-90">
          {/* Background track */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            stroke="#E2E8F0"
            strokeWidth="14"
            fill="transparent"
            strokeDasharray={circumference}
            strokeDashoffset={circumference * 0.25}
            strokeLinecap="round"
          />
          {/* Active progress arc */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            stroke={config.color}
            strokeWidth="14"
            fill="transparent"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            className="transition-all duration-700 ease-out"
          />
        </svg>

        {/* Center Readout */}
        <div className="absolute inset-0 flex flex-col items-center justify-center pt-2">
          <span className="text-3xl font-black tracking-tight" style={{ color: config.color }}>
            {depthCm} <span className="text-sm font-bold">cm</span>
          </span>
          <span className="text-[11px] font-extrabold text-typography-secondary mt-0.5 uppercase tracking-wider">
            {percentage.toFixed(0)}% Capacity
          </span>
        </div>
      </div>
    </div>
  );
}
