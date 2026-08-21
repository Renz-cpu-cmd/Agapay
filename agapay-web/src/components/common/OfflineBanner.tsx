import React from 'react';
import { WifiOff, RefreshCw } from 'lucide-react';

interface OfflineBannerProps {
  onRetry?: () => void;
}

export function OfflineBanner({ onRetry }: OfflineBannerProps) {
  return (
    <div className="bg-slate-800 text-white px-4 py-2.5 flex items-center justify-between text-xs font-semibold shadow-md">
      <div className="flex items-center gap-2">
        <WifiOff size={16} className="text-amber-400 animate-pulse" />
        <span>
          <strong className="text-amber-300 uppercase tracking-wider">OFFLINE MODE:</strong> Live WebSocket disconnected. Displaying cached local disaster telemetry.
        </span>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="flex items-center gap-1 bg-slate-700 hover:bg-slate-600 px-3 py-1 rounded text-xs text-white transition-colors"
        >
          <RefreshCw size={12} />
          Reconnect
        </button>
      )}
    </div>
  );
}
