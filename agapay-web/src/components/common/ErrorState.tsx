import React from 'react';
import { AlertOctagon } from 'lucide-react';

interface ErrorStateProps {
  title?: string;
  message?: string;
  onRetry?: () => void;
}

export function ErrorState({
  title = 'Failed to Load Telemetry',
  message = 'Unable to connect to the monitoring services. Please check network connection.',
  onRetry,
}: ErrorStateProps) {
  return (
    <div className="flex flex-col items-center justify-center p-10 text-center bg-white rounded-xl border border-alert-evacuate/30 shadow-card">
      <div className="p-4 rounded-full bg-alert-evacuateBg text-alert-evacuate mb-3">
        <AlertOctagon size={36} />
      </div>
      <h4 className="text-base font-extrabold text-typography-primary">{title}</h4>
      <p className="text-sm text-typography-secondary max-w-sm mt-1">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-4 px-4 py-2 text-xs font-bold text-white bg-alert-evacuate hover:bg-red-700 rounded-lg shadow-sm transition-colors"
        >
          Retry Connection
        </button>
      )}
    </div>
  );
}
