'use client';

import React, { useState } from 'react';
import { useDashboard } from '@/context/DashboardContext';
import {
  Bell,
  Radio,
  Wifi,
  WifiOff,
  User,
  LogOut,
  ShieldCheck,
  ChevronDown,
} from 'lucide-react';
import { ManualAlertModal } from '@/components/modals/ManualAlertModal';
import { StatusBadge } from '@/components/common/StatusBadge';
import { formatRelativeTime } from '@/lib/formatters';
import Link from 'next/link';

interface TopHeaderProps {
  sidebarCollapsed: boolean;
}

export function TopHeader({ sidebarCollapsed }: TopHeaderProps) {
  const {
    isOffline,
    currentUser,
    selectedBarangay,
    setSelectedBarangay,
    alerts,
    metrics,
    resolveAlert,
    toggleOfflineMode,
  } = useDashboard();

  const [isAlertModalOpen, setIsAlertModalOpen] = useState(false);
  const [isNotificationOpen, setIsNotificationOpen] = useState(false);
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);

  const activeAlerts = alerts.filter((a) => a.status !== 'Resolved');

  return (
    <>
      <header
        className={`fixed top-0 right-0 h-16 z-30 bg-white border-b border-border-light flex items-center justify-between px-6 transition-all duration-300 ${
          sidebarCollapsed ? 'left-20' : 'left-64'
        }`}
      >
        {/* Left: Jurisdiction Zone Filter */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold text-typography-secondary uppercase">Sector:</span>
            <select
              value={selectedBarangay}
              onChange={(e) => setSelectedBarangay(e.target.value)}
              className="text-xs font-extrabold text-typography-primary bg-surface-secondary border border-border-light rounded-lg px-3 py-1.5 focus:ring-2 focus:ring-brand-secondary outline-none cursor-pointer"
            >
              <option value="All Barangays">All Barangays (Command Overview)</option>
              <option value="Brgy. San Nicolas">Brgy. San Nicolas</option>
              <option value="Brgy. Poblacion">Brgy. Poblacion</option>
              <option value="Brgy. San Vicente">Brgy. San Vicente</option>
              <option value="Brgy. Santa Cruz">Brgy. Santa Cruz</option>
              <option value="Brgy. Santo Rosario">Brgy. Santo Rosario</option>
            </select>
          </div>

          {/* Connection Status Pill */}
          <button
            onClick={toggleOfflineMode}
            title="Click to toggle simulated online/offline state"
            className={`flex items-center gap-2 px-2.5 py-1 rounded-full text-xs font-black border transition-all ${
              isOffline
                ? 'bg-slate-100 text-slate-700 border-slate-300'
                : 'bg-emerald-50 text-emerald-800 border-emerald-300'
            }`}
          >
            {isOffline ? (
              <>
                <WifiOff size={13} className="text-slate-500" />
                <span>OFFLINE SIMULATION</span>
              </>
            ) : (
              <>
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                <span>SYSTEM ONLINE</span>
              </>
            )}
          </button>
        </div>

        {/* Right Actions */}
        <div className="flex items-center gap-3">
          {/* Quick Broadcast Button */}
          <button
            onClick={() => setIsAlertModalOpen(true)}
            className="flex items-center gap-2 px-3.5 py-1.5 bg-alert-warning hover:bg-orange-600 text-white rounded-xl text-xs font-extrabold shadow-sm transition-transform active:scale-95"
          >
            <Radio size={14} className="animate-pulse" />
            <span>Broadcast Alert</span>
          </button>

          {/* Notifications Bell Dropdown */}
          <div className="relative">
            <button
              onClick={() => {
                setIsNotificationOpen(!isNotificationOpen);
                setIsUserMenuOpen(false);
              }}
              className="p-2 rounded-xl text-typography-secondary hover:text-typography-primary hover:bg-surface-secondary relative transition-colors"
            >
              <Bell size={20} />
              {activeAlerts.length > 0 && (
                <span className="absolute top-1 right-1 w-4 h-4 bg-alert-evacuate text-white text-[9px] font-black rounded-full flex items-center justify-center">
                  {activeAlerts.length}
                </span>
              )}
            </button>

            {isNotificationOpen && (
              <div className="absolute right-0 mt-2 w-80 bg-white rounded-2xl border border-border-light shadow-2xl p-4 z-50 animate-in fade-in zoom-in-95">
                <div className="flex items-center justify-between pb-2 border-b border-border-light">
                  <h4 className="text-xs font-black text-typography-primary uppercase">Active Emergencies ({activeAlerts.length})</h4>
                  <Link
                    href="/alerts"
                    onClick={() => setIsNotificationOpen(false)}
                    className="text-[11px] font-bold text-brand-primary hover:underline"
                  >
                    View All
                  </Link>
                </div>
                <div className="mt-2 space-y-2 max-h-72 overflow-y-auto">
                  {activeAlerts.length === 0 ? (
                    <p className="text-xs text-typography-muted text-center py-4">No active emergency alerts.</p>
                  ) : (
                    activeAlerts.map((a) => (
                      <div key={a.id} className="p-2.5 rounded-xl bg-surface-secondary border border-border-light">
                        <div className="flex items-center justify-between">
                          <StatusBadge level={a.severity} size="sm" />
                          <span className="text-[10px] text-typography-muted">{formatRelativeTime(a.createdAt)}</span>
                        </div>
                        <p className="text-xs font-bold text-typography-primary mt-1.5">{a.stationName}</p>
                        <p className="text-[11px] text-typography-secondary line-clamp-2 mt-0.5">{a.message}</p>
                        <div className="mt-2 flex justify-end">
                          <button
                            onClick={() => resolveAlert(a.id)}
                            className="text-[10px] font-bold text-brand-primary hover:underline"
                          >
                            Mark Resolved
                          </button>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}
          </div>

          {/* User Profile Pill */}
          <div className="relative">
            <button
              onClick={() => {
                setIsUserMenuOpen(!isUserMenuOpen);
                setIsNotificationOpen(false);
              }}
              className="flex items-center gap-2 pl-2 pr-3 py-1.5 rounded-xl hover:bg-surface-secondary border border-border-light transition-colors"
            >
              <div className="w-7 h-7 rounded-lg bg-brand-primary flex items-center justify-center text-white text-xs font-extrabold">
                {currentUser.name[0]}
              </div>
              <div className="text-left hidden sm:block">
                <p className="text-xs font-extrabold text-typography-primary leading-tight">{currentUser.name}</p>
                <p className="text-[10px] font-bold text-typography-muted">{currentUser.badge}</p>
              </div>
              <ChevronDown size={14} className="text-typography-muted" />
            </button>

            {isUserMenuOpen && (
              <div className="absolute right-0 mt-2 w-56 bg-white rounded-2xl border border-border-light shadow-2xl p-2 z-50 animate-in fade-in zoom-in-95">
                <div className="p-2.5 border-b border-border-light">
                  <p className="text-xs font-black text-typography-primary">{currentUser.name}</p>
                  <p className="text-[11px] text-typography-secondary">{currentUser.email}</p>
                  <p className="text-[10px] font-bold text-brand-secondary mt-1">{currentUser.role}</p>
                </div>
                <div className="py-1">
                  <Link
                    href="/settings"
                    onClick={() => setIsUserMenuOpen(false)}
                    className="flex items-center gap-2 px-3 py-2 text-xs font-semibold text-typography-secondary hover:text-typography-primary hover:bg-surface-secondary rounded-lg"
                  >
                    <ShieldCheck size={14} /> Security & Account
                  </Link>
                  <Link
                    href="/login"
                    onClick={() => setIsUserMenuOpen(false)}
                    className="flex items-center gap-2 px-3 py-2 text-xs font-bold text-alert-evacuate hover:bg-alert-evacuateBg rounded-lg"
                  >
                    <LogOut size={14} /> Sign Out
                  </Link>
                </div>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Manual Alert Modal */}
      <ManualAlertModal isOpen={isAlertModalOpen} onClose={() => setIsAlertModalOpen(false)} />
    </>
  );
}
