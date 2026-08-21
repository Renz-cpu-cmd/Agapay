import React from 'react';
import { AlertLevel, ALERT_CONFIGS } from '@/constants/theme';
import { CheckCircle2, AlertTriangle, AlertCircle, Siren } from 'lucide-react';

interface StatusBadgeProps {
  level: AlertLevel;
  size?: 'sm' | 'md' | 'lg';
  showIcon?: boolean;
  className?: string;
}

export function StatusBadge({ level, size = 'md', showIcon = true, className = '' }: StatusBadgeProps) {
  const config = ALERT_CONFIGS[level] || ALERT_CONFIGS.NORMAL;

  const sizeClasses = {
    sm: 'px-2 py-0.5 text-xs font-bold gap-1',
    md: 'px-2.5 py-1 text-xs font-extrabold gap-1.5',
    lg: 'px-3.5 py-1.5 text-sm font-black gap-2',
  };

  const iconSizes = {
    sm: 12,
    md: 14,
    lg: 16,
  };

  const getIcon = () => {
    switch (level) {
      case 'NORMAL':
        return <CheckCircle2 size={iconSizes[size]} />;
      case 'ADVISORY':
        return <AlertCircle size={iconSizes[size]} />;
      case 'WARNING':
        return <AlertTriangle size={iconSizes[size]} />;
      case 'EVACUATE':
        return <Siren size={iconSizes[size]} className="animate-pulse" />;
    }
  };

  return (
    <span
      className={`inline-flex items-center rounded-full border shadow-sm transition-colors ${sizeClasses[size]} ${className}`}
      style={{
        backgroundColor: config.bgColor,
        color: config.textColor,
        borderColor: config.borderColor,
      }}
    >
      {showIcon && getIcon()}
      <span className="tracking-wide uppercase">{config.code}</span>
    </span>
  );
}
