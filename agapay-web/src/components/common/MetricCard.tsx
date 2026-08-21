import React, { ReactNode } from 'react';

interface MetricCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: ReactNode;
  trend?: {
    value: string;
    isPositive?: boolean;
    isNegative?: boolean;
  };
  accentColor?: string;
  onClick?: () => void;
}

export function MetricCard({
  title,
  value,
  subtitle,
  icon,
  trend,
  accentColor,
  onClick,
}: MetricCardProps) {
  return (
    <div
      onClick={onClick}
      className={`bg-white rounded-xl p-5 border border-border-light shadow-card transition-all ${
        onClick ? 'cursor-pointer hover:shadow-cardHover hover:border-brand-secondary/40' : ''
      }`}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-bold text-typography-secondary uppercase tracking-wider">{title}</p>
          <h3
            className="text-3xl font-black tracking-tight mt-1"
            style={{ color: accentColor || '#172033' }}
          >
            {value}
          </h3>
          {subtitle && <p className="text-xs text-typography-muted mt-1 font-medium">{subtitle}</p>}
        </div>
        <div
          className="p-3 rounded-xl flex items-center justify-center"
          style={{
            backgroundColor: accentColor ? `${accentColor}18` : '#F1F5F9',
            color: accentColor || '#0B3D91',
          }}
        >
          {icon}
        </div>
      </div>

      {trend && (
        <div className="mt-3 pt-3 border-t border-border-light flex items-center text-xs font-semibold">
          <span
            className={
              trend.isNegative
                ? 'text-alert-evacuate'
                : trend.isPositive
                ? 'text-alert-normal'
                : 'text-typography-secondary'
            }
          >
            {trend.value}
          </span>
        </div>
      )}
    </div>
  );
}
