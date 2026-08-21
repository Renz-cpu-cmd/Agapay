'use client';

import React, { useState } from 'react';
import { NavigationShell } from '@/components/layout/NavigationShell';
import { useDashboard } from '@/context/DashboardContext';
import { StatusBadge } from '@/components/common/StatusBadge';
import { AlertLevel } from '@/constants/theme';
import { StationStatus } from '@/models/station';
import {
  Search,
  Filter,
  ArrowUpDown,
  Radio,
  ExternalLink,
  SlidersHorizontal,
  BatteryCharging,
  Wifi,
} from 'lucide-react';
import { formatWaterLevel, formatRainfall, formatBattery, formatRelativeTime } from '@/lib/formatters';
import Link from 'next/link';

export default function StationsPage() {
  const { stations } = useDashboard();
  const [searchQuery, setSearchQuery] = useState('');
  const [alertFilter, setAlertFilter] = useState<string>('ALL');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [sortBy, setSortBy] = useState<'depth' | 'name' | 'battery'>('depth');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');

  // Filtering
  const filtered = stations.filter((s) => {
    const matchesSearch =
      s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.barangay.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.id.toLowerCase().includes(searchQuery.toLowerCase());

    const matchesAlert = alertFilter === 'ALL' || s.alertLevel === alertFilter;
    const matchesStatus = statusFilter === 'ALL' || s.status === statusFilter;

    return matchesSearch && matchesAlert && matchesStatus;
  });

  // Sorting
  const sorted = [...filtered].sort((a, b) => {
    let comp = 0;
    if (sortBy === 'depth') comp = a.waterDepthCm - b.waterDepthCm;
    if (sortBy === 'name') comp = a.name.localeCompare(b.name);
    if (sortBy === 'battery') comp = a.batteryPercent - b.batteryPercent;
    return sortOrder === 'desc' ? -comp : comp;
  });

  const toggleSort = (field: 'depth' | 'name' | 'battery') => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortOrder('desc');
    }
  };

  return (
    <NavigationShell>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-black text-typography-primary tracking-tight">
              Sensor Stations Directory
            </h1>
            <p className="text-xs font-semibold text-typography-secondary mt-0.5">
              Live fleet management for ESP32 river gauge stations ({stations.length} installed)
            </p>
          </div>
        </div>

        {/* Filter & Search Bar */}
        <div className="bg-white p-4 rounded-2xl border border-border-light shadow-card flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="relative w-full md:w-80">
            <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-typography-muted" />
            <input
              type="text"
              placeholder="Search station, barangay, or ID..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full text-xs font-semibold pl-10 pr-4 py-2 rounded-xl border border-border-light bg-surface-secondary focus:bg-white focus:ring-2 focus:ring-brand-secondary outline-none"
            />
          </div>

          <div className="flex flex-wrap items-center gap-3 w-full md:w-auto">
            {/* Alert Level Filter */}
            <div className="flex items-center gap-1.5 text-xs">
              <span className="font-bold text-typography-secondary">Alert:</span>
              <select
                value={alertFilter}
                onChange={(e) => setAlertFilter(e.target.value)}
                className="text-xs font-bold p-2 rounded-xl border border-border-light bg-surface-secondary outline-none cursor-pointer"
              >
                <option value="ALL">All Alert Levels</option>
                <option value="NORMAL">Normal</option>
                <option value="ADVISORY">Advisory</option>
                <option value="WARNING">Warning</option>
                <option value="EVACUATE">Evacuate</option>
              </select>
            </div>

            {/* Status Filter */}
            <div className="flex items-center gap-1.5 text-xs">
              <span className="font-bold text-typography-secondary">Hardware:</span>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="text-xs font-bold p-2 rounded-xl border border-border-light bg-surface-secondary outline-none cursor-pointer"
              >
                <option value="ALL">All Hardware Status</option>
                <option value="Online">Online</option>
                <option value="Offline">Offline</option>
                <option value="Maintenance">Maintenance</option>
              </select>
            </div>
          </div>
        </div>

        {/* Stations Table */}
        <div className="bg-white rounded-2xl border border-border-light shadow-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-surface-secondary/70 border-b border-border-light text-[11px] font-black text-typography-secondary uppercase tracking-wider">
                  <th
                    onClick={() => toggleSort('name')}
                    className="py-3.5 px-4 cursor-pointer hover:text-typography-primary"
                  >
                    <div className="flex items-center gap-1">
                      <span>Station & Location</span>
                      <ArrowUpDown size={12} />
                    </div>
                  </th>
                  <th
                    onClick={() => toggleSort('depth')}
                    className="py-3.5 px-4 cursor-pointer hover:text-typography-primary"
                  >
                    <div className="flex items-center gap-1">
                      <span>Water Depth</span>
                      <ArrowUpDown size={12} />
                    </div>
                  </th>
                  <th className="py-3.5 px-4">Rainfall</th>
                  <th
                    onClick={() => toggleSort('battery')}
                    className="py-3.5 px-4 cursor-pointer hover:text-typography-primary"
                  >
                    <div className="flex items-center gap-1">
                      <span>Battery / Power</span>
                      <ArrowUpDown size={12} />
                    </div>
                  </th>
                  <th className="py-3.5 px-4">Hardware Status</th>
                  <th className="py-3.5 px-4">Alert Level</th>
                  <th className="py-3.5 px-4">Last Ping</th>
                  <th className="py-3.5 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-light text-xs font-semibold">
                {sorted.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="py-12 text-center text-typography-muted">
                      No monitoring stations found matching filters.
                    </td>
                  </tr>
                ) : (
                  sorted.map((st) => {
                    const isOnline = st.status === 'Online';
                    return (
                      <tr key={st.id} className="hover:bg-surface-secondary/50 transition-colors">
                        <td className="py-4 px-4">
                          <div>
                            <Link
                              href={`/stations/${st.id}`}
                              className="font-extrabold text-brand-primary hover:underline text-sm block"
                            >
                              {st.name}
                            </Link>
                            <span className="text-typography-secondary text-[11px]">
                              {st.barangay} · <span className="font-mono text-typography-muted">{st.id}</span>
                            </span>
                          </div>
                        </td>

                        <td className="py-4 px-4">
                          <div className="font-black text-sm text-typography-primary">
                            {formatWaterLevel(st.waterDepthCm)}
                          </div>
                          <span className="text-[10px] text-typography-muted">
                            Max: {st.maxThresholdCm} cm
                          </span>
                        </td>

                        <td className="py-4 px-4 font-bold text-typography-primary">
                          {formatRainfall(st.rainfallMm)}
                        </td>

                        <td className="py-4 px-4">
                          <div className="flex items-center gap-1.5">
                            <span
                              className={`w-2 h-2 rounded-full ${
                                st.batteryPercent > 80
                                  ? 'bg-alert-normal'
                                  : st.batteryPercent > 40
                                  ? 'bg-alert-advisory'
                                  : 'bg-alert-evacuate'
                              }`}
                            ></span>
                            <span className="font-bold">{formatBattery(st.batteryPercent)}</span>
                          </div>
                          <span className="text-[10px] text-typography-muted block">
                            {st.solarCharging ? 'Solar charging' : 'On battery'}
                          </span>
                        </td>

                        <td className="py-4 px-4">
                          <span
                            className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-extrabold ${
                              isOnline
                                ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                                : st.status === 'Maintenance'
                                ? 'bg-amber-50 text-amber-800 border border-amber-200'
                                : 'bg-rose-50 text-rose-800 border border-rose-200'
                            }`}
                          >
                            <span
                              className={`w-1.5 h-1.5 rounded-full ${
                                isOnline ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500'
                              }`}
                            ></span>
                            {st.status}
                          </span>
                        </td>

                        <td className="py-4 px-4">
                          <StatusBadge level={st.alertLevel} size="sm" />
                        </td>

                        <td className="py-4 px-4 text-typography-secondary text-[11px]">
                          {formatRelativeTime(st.lastPing)}
                        </td>

                        <td className="py-4 px-4 text-right">
                          <Link
                            href={`/stations/${st.id}`}
                            className="inline-flex items-center gap-1 px-3 py-1.5 bg-surface-secondary hover:bg-brand-primary hover:text-white rounded-xl font-extrabold text-xs transition-colors"
                          >
                            <span>Inspect</span>
                            <ExternalLink size={12} />
                          </Link>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </NavigationShell>
  );
}
