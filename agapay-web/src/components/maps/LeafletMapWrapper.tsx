'use client';

import dynamic from 'next/dynamic';
import React from 'react';
import { Station } from '@/models/station';
import { SOSBeacon } from '@/models/sos';
import { Loader2 } from 'lucide-react';

const DynamicMap = dynamic(
  () => import('./LeafletMap').then((mod) => mod.LeafletMap),
  {
    ssr: false,
    loading: () => (
      <div className="w-full h-[480px] bg-slate-100 rounded-xl border border-border-light flex flex-col items-center justify-center text-typography-secondary">
        <Loader2 className="w-8 h-8 animate-spin text-brand-primary mb-2" />
        <span className="text-xs font-bold">Initializing GIS Flood Operations Map...</span>
      </div>
    ),
  }
);

interface LeafletMapWrapperProps {
  stations: Station[];
  sosBeacons?: SOSBeacon[];
  selectedStationId?: string;
  onSelectStation?: (station: Station) => void;
  height?: string;
  center?: [number, number];
  zoom?: number;
}

export function LeafletMapWrapper(props: LeafletMapWrapperProps) {
  return <DynamicMap {...props} />;
}
