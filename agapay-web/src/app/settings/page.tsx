'use client';

import React, { useState } from 'react';
import { NavigationShell } from '@/components/layout/NavigationShell';
import { useDashboard } from '@/context/DashboardContext';
import { APP_CONFIG } from '@/constants/theme';
import {
  Settings,
  Shield,
  Bell,
  MapPin,
  Save,
  CheckCircle2,
  Sliders,
  Radio,
  Lock,
} from 'lucide-react';

export default function SettingsPage() {
  const { currentUser, isOffline, toggleOfflineMode } = useDashboard();
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Form states
  const [defaultAdvisory, setDefaultAdvisory] = useState(45);
  const [defaultWarning, setDefaultWarning] = useState(75);
  const [defaultEvacuate, setDefaultEvacuate] = useState(90);
  const [enableSmsGateway, setEnableSmsGateway] = useState(true);
  const [enableFcmPush, setEnableFcmPush] = useState(true);
  const [sessionTimeoutMinutes, setSessionTimeoutMinutes] = useState(60);

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    setSaveSuccess(true);
    setTimeout(() => setSaveSuccess(false), 3000);
  };

  return (
    <NavigationShell>
      <div className="space-y-6 max-w-4xl">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-black text-typography-primary tracking-tight">
              Command Dashboard Settings & Policies
            </h1>
            <p className="text-xs font-semibold text-typography-secondary mt-0.5">
              System-wide flood thresholds, notification channels, and officer security configurations
            </p>
          </div>
        </div>

        {saveSuccess && (
          <div className="p-3.5 bg-emerald-50 text-emerald-900 border border-emerald-300 rounded-xl text-xs font-bold flex items-center gap-2 animate-in fade-in">
            <CheckCircle2 size={16} className="text-emerald-600" />
            <span>Dashboard configuration saved and applied to active operations dispatch nodes.</span>
          </div>
        )}

        <form onSubmit={handleSave} className="space-y-6">
          {/* Section 1: Account Profile */}
          <div className="bg-white p-6 rounded-2xl border border-border-light shadow-card space-y-4">
            <div className="flex items-center gap-2.5 pb-3 border-b border-border-light">
              <Shield size={18} className="text-brand-primary" />
              <h3 className="text-sm font-black text-typography-primary uppercase">
                Active Officer Profile
              </h3>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-bold text-typography-secondary uppercase mb-1">
                  Officer Name
                </label>
                <input
                  type="text"
                  value={currentUser.name}
                  disabled
                  className="w-full text-xs font-semibold p-2.5 rounded-xl border border-border-light bg-surface-secondary text-typography-muted outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-typography-secondary uppercase mb-1">
                  Designation / Role
                </label>
                <input
                  type="text"
                  value={currentUser.role}
                  disabled
                  className="w-full text-xs font-semibold p-2.5 rounded-xl border border-border-light bg-surface-secondary text-typography-muted outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-typography-secondary uppercase mb-1">
                  Official Email
                </label>
                <input
                  type="text"
                  value={currentUser.email}
                  disabled
                  className="w-full text-xs font-semibold p-2.5 rounded-xl border border-border-light bg-surface-secondary text-typography-muted outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-typography-secondary uppercase mb-1">
                  Command Badge Number
                </label>
                <input
                  type="text"
                  value={currentUser.badge}
                  disabled
                  className="w-full text-xs font-semibold p-2.5 rounded-xl border border-border-light bg-surface-secondary text-typography-muted outline-none font-mono"
                />
              </div>
            </div>
          </div>

          {/* Section 2: Global Threshold Defaults */}
          <div className="bg-white p-6 rounded-2xl border border-border-light shadow-card space-y-4">
            <div className="flex items-center gap-2.5 pb-3 border-b border-border-light">
              <Sliders size={18} className="text-brand-primary" />
              <h3 className="text-sm font-black text-typography-primary uppercase">
                Default Sensor Trigger Thresholds
              </h3>
            </div>

            <p className="text-xs text-typography-secondary leading-relaxed">
              Default baseline thresholds applied when initializing new ESP32 ultrasonic river stations.
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-bold text-alert-advisoryText uppercase mb-1">
                  Advisory Tier (cm)
                </label>
                <input
                  type="number"
                  value={defaultAdvisory}
                  onChange={(e) => setDefaultAdvisory(Number(e.target.value))}
                  className="w-full text-xs font-bold p-2.5 rounded-xl border border-yellow-300 bg-yellow-50 focus:bg-white outline-none"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-alert-warningText uppercase mb-1">
                  Warning Tier (cm)
                </label>
                <input
                  type="number"
                  value={defaultWarning}
                  onChange={(e) => setDefaultWarning(Number(e.target.value))}
                  className="w-full text-xs font-bold p-2.5 rounded-xl border border-orange-300 bg-orange-50 focus:bg-white outline-none"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-alert-evacuateText uppercase mb-1">
                  Evacuation Tier (cm)
                </label>
                <input
                  type="number"
                  value={defaultEvacuate}
                  onChange={(e) => setDefaultEvacuate(Number(e.target.value))}
                  className="w-full text-xs font-bold p-2.5 rounded-xl border border-red-300 bg-red-50 focus:bg-white outline-none"
                  required
                />
              </div>
            </div>
          </div>

          {/* Section 3: Notification Broadcast Channels */}
          <div className="bg-white p-6 rounded-2xl border border-border-light shadow-card space-y-4">
            <div className="flex items-center gap-2.5 pb-3 border-b border-border-light">
              <Bell size={18} className="text-brand-primary" />
              <h3 className="text-sm font-black text-typography-primary uppercase">
                Broadcast Channels & SMS Gateways
              </h3>
            </div>

            <div className="space-y-3 text-xs">
              <label className="flex items-center justify-between p-3 rounded-xl bg-surface-secondary border border-border-light cursor-pointer">
                <div>
                  <span className="font-extrabold text-typography-primary block">
                    Citizen FCM Mobile App Push Notifications
                  </span>
                  <span className="text-typography-secondary">
                    Transmit immediate push banners to all citizen devices on alert triggers
                  </span>
                </div>
                <input
                  type="checkbox"
                  checked={enableFcmPush}
                  onChange={(e) => setEnableFcmPush(e.target.checked)}
                  className="w-4 h-4 text-brand-primary rounded"
                />
              </label>

              <label className="flex items-center justify-between p-3 rounded-xl bg-surface-secondary border border-border-light cursor-pointer">
                <div>
                  <span className="font-extrabold text-typography-primary block">
                    Barangay Emergency SMS Broadcast Gateway
                  </span>
                  <span className="text-typography-secondary">
                    Send mass SMS alerts via NDRRMC/Telco cell-broadcast relays
                  </span>
                </div>
                <input
                  type="checkbox"
                  checked={enableSmsGateway}
                  onChange={(e) => setEnableSmsGateway(e.target.checked)}
                  className="w-4 h-4 text-brand-primary rounded"
                />
              </label>
            </div>
          </div>

          {/* Section 4: Security & Diagnostics */}
          <div className="bg-white p-6 rounded-2xl border border-border-light shadow-card space-y-4">
            <div className="flex items-center gap-2.5 pb-3 border-b border-border-light">
              <Lock size={18} className="text-brand-primary" />
              <h3 className="text-sm font-black text-typography-primary uppercase">
                Session Security & Diagnostics
              </h3>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-bold text-typography-secondary uppercase mb-1">
                  JWT Session Inactivity Timeout (Minutes)
                </label>
                <input
                  type="number"
                  value={sessionTimeoutMinutes}
                  onChange={(e) => setSessionTimeoutMinutes(Number(e.target.value))}
                  className="w-full text-xs font-bold p-2.5 rounded-xl border border-border-light bg-surface-secondary focus:bg-white outline-none"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-typography-secondary uppercase mb-1">
                  Diagnostic Offline Simulation
                </label>
                <button
                  type="button"
                  onClick={toggleOfflineMode}
                  className={`w-full py-2.5 px-3 rounded-xl text-xs font-black border text-left flex items-center justify-between ${
                    isOffline
                      ? 'bg-amber-100 text-amber-900 border-amber-300'
                      : 'bg-emerald-100 text-emerald-900 border-emerald-300'
                  }`}
                >
                  <span>{isOffline ? 'OFFLINE SIMULATOR ACTIVE' : 'LIVE ONLINE MODE'}</span>
                  <span className="text-[10px] uppercase underline">Toggle</span>
                </button>
              </div>
            </div>
          </div>

          {/* Submit */}
          <div className="flex justify-end pt-2">
            <button
              type="submit"
              className="flex items-center gap-2 px-6 py-2.5 bg-brand-primary hover:bg-brand-primaryDark text-white text-xs font-black rounded-xl shadow-lg shadow-brand-primary/20 transition-all active:scale-95"
            >
              <Save size={16} />
              <span>Save System Settings</span>
            </button>
          </div>
        </form>
      </div>
    </NavigationShell>
  );
}
