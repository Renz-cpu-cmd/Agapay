import React from 'react';
import { Loader2 } from 'lucide-react';

export function LoadingState({ message = 'Loading emergency operations telemetry...' }: { message?: string }) {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-center">
      <Loader2 className="w-8 h-8 animate-spin text-brand-primary" />
      <p className="text-sm font-semibold text-typography-secondary mt-3">{message}</p>
    </div>
  );
}
