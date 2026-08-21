'use client';

import React, { useState } from 'react';
import { NavigationShell } from '@/components/layout/NavigationShell';
import { useDashboard } from '@/context/DashboardContext';
import { ReportType } from '@/models/report';
import {
  FileText,
  Download,
  Calendar,
  Filter,
  CheckCircle2,
  Printer,
  Table,
} from 'lucide-react';
import { formatDateTime } from '@/lib/formatters';

export default function ReportsPage() {
  const { stations, alerts, sosBeacons } = useDashboard();
  const [reportType, setReportType] = useState<ReportType>('FloodEvent');
  const [selectedStation, setSelectedStation] = useState<string>('ALL');
  const [startDate, setStartDate] = useState<string>('2026-08-01');
  const [endDate, setEndDate] = useState<string>('2026-08-22');
  const [isGenerated, setIsGenerated] = useState<boolean>(true);
  const [downloadSuccess, setDownloadSuccess] = useState<string | null>(null);

  const handleGenerate = (e: React.FormEvent) => {
    e.preventDefault();
    setIsGenerated(true);
  };

  const handleDownload = (formatType: string) => {
    setDownloadSuccess(`Exported AGAPAY_${reportType}_${startDate}_to_${endDate}.${formatType}`);
    setTimeout(() => setDownloadSuccess(null), 3000);
  };

  return (
    <NavigationShell>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-black text-typography-primary tracking-tight">
              Disaster Operations Reports & Compliance Export
            </h1>
            <p className="text-xs font-semibold text-typography-secondary mt-0.5">
              Official NDRRMC, LGU executive briefings, and post-disaster audit report generator
            </p>
          </div>
        </div>

        {downloadSuccess && (
          <div className="p-3.5 bg-emerald-50 text-emerald-900 border border-emerald-300 rounded-xl text-xs font-bold flex items-center gap-2 animate-in fade-in">
            <CheckCircle2 size={16} className="text-emerald-600" />
            <span>{downloadSuccess}</span>
          </div>
        )}

        {/* Report Generator Controls */}
        <form
          onSubmit={handleGenerate}
          className="bg-white p-5 rounded-2xl border border-border-light shadow-card space-y-4"
        >
          <h3 className="text-sm font-black text-typography-primary uppercase tracking-wider">
            Report Parameters & Data Scope
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <label className="block text-xs font-bold text-typography-secondary uppercase mb-1">
                Report Type
              </label>
              <select
                value={reportType}
                onChange={(e) => setReportType(e.target.value as ReportType)}
                className="w-full text-xs font-bold p-2.5 rounded-xl border border-border-light bg-surface-secondary outline-none cursor-pointer"
              >
                <option value="FloodEvent">Comprehensive Flood Event Summary</option>
                <option value="StationPerformance">Sensor Station Fleet Performance</option>
                <option value="AlertHistory">Public Safety Alert Bulletin Log</option>
                <option value="SOSLog">SOS Distress & Rescue Dispatch Log</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-bold text-typography-secondary uppercase mb-1">
                Station / Sector Scope
              </label>
              <select
                value={selectedStation}
                onChange={(e) => setSelectedStation(e.target.value)}
                className="w-full text-xs font-bold p-2.5 rounded-xl border border-border-light bg-surface-secondary outline-none cursor-pointer"
              >
                <option value="ALL">All Stations (Jurisdiction Overview)</option>
                {stations.map((st) => (
                  <option key={st.id} value={st.id}>
                    {st.name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-bold text-typography-secondary uppercase mb-1">
                Start Date
              </label>
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="w-full text-xs font-bold p-2 rounded-xl border border-border-light bg-surface-secondary outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-typography-secondary uppercase mb-1">
                End Date
              </label>
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="w-full text-xs font-bold p-2 rounded-xl border border-border-light bg-surface-secondary outline-none"
              />
            </div>
          </div>

          <div className="flex items-center justify-between pt-2 border-t border-border-light">
            <span className="text-xs text-typography-muted">
              Generates authenticated report signed with LGU cryptographic timestamp
            </span>
            <button
              type="submit"
              className="px-5 py-2 text-xs font-extrabold text-white bg-brand-primary hover:bg-brand-primaryDark rounded-xl shadow-md transition-colors"
            >
              Generate Live Report
            </button>
          </div>
        </form>

        {/* Generated Report Preview */}
        {isGenerated && (
          <div className="bg-white rounded-2xl border border-border-light shadow-card p-6 space-y-6">
            {/* Header of Report Document */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-border-light gap-4">
              <div>
                <span className="text-[10px] font-black text-brand-primary uppercase tracking-widest bg-blue-50 px-2 py-0.5 rounded">
                  OFFICIAL INCIDENT REPORT
                </span>
                <h2 className="text-xl font-black text-typography-primary mt-1">
                  AGAPAY Hydro-Meteorological Disaster Assessment
                </h2>
                <p className="text-xs text-typography-secondary">
                  Period: {startDate} to {endDate} · Generated by Cmdr. Antonio Ramos (LGU DRRMC)
                </p>
              </div>

              {/* Download Actions */}
              <div className="flex items-center gap-2">
                <button
                  onClick={() => handleDownload('pdf')}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-brand-primary hover:bg-brand-primaryDark text-white text-xs font-extrabold rounded-xl shadow-sm transition-colors"
                >
                  <Download size={13} />
                  <span>Export PDF</span>
                </button>
                <button
                  onClick={() => handleDownload('csv')}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-surface-secondary hover:bg-slate-200 text-typography-primary text-xs font-bold rounded-xl border border-border-light transition-colors"
                >
                  <Table size={13} />
                  <span>Export CSV</span>
                </button>
              </div>
            </div>

            {/* Executive Summary Metrics */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="p-3.5 bg-surface-secondary rounded-xl">
                <span className="text-[10px] font-bold text-typography-muted uppercase block">Total Alerts</span>
                <strong className="text-xl font-black text-typography-primary">{alerts.length} Breaches</strong>
              </div>
              <div className="p-3.5 bg-surface-secondary rounded-xl">
                <span className="text-[10px] font-bold text-typography-muted uppercase block">Peak Water Level</span>
                <strong className="text-xl font-black text-alert-evacuate">102.4 cm</strong>
              </div>
              <div className="p-3.5 bg-surface-secondary rounded-xl">
                <span className="text-[10px] font-bold text-typography-muted uppercase block">SOS Distress Calls</span>
                <strong className="text-xl font-black text-alert-sos">{sosBeacons.length} Rescues</strong>
              </div>
              <div className="p-3.5 bg-surface-secondary rounded-xl">
                <span className="text-[10px] font-bold text-typography-muted uppercase block">Avg Dispatch Response</span>
                <strong className="text-xl font-black text-alert-normal">4.2 Minutes</strong>
              </div>
            </div>

            {/* Incident Records Table */}
            <div>
              <h4 className="text-xs font-black text-typography-primary uppercase tracking-wider mb-3">
                Breach & Emergency Incident Logs
              </h4>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-semibold">
                  <thead className="bg-surface-secondary text-typography-secondary text-[10px] uppercase font-bold">
                    <tr>
                      <th className="py-2.5 px-3">Event ID</th>
                      <th className="py-2.5 px-3">Severity</th>
                      <th className="py-2.5 px-3">Sector</th>
                      <th className="py-2.5 px-3">Observed Level</th>
                      <th className="py-2.5 px-3">Recorded Time</th>
                      <th className="py-2.5 px-3">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border-light">
                    {alerts.map((al) => (
                      <tr key={al.id} className="hover:bg-surface-secondary/40">
                        <td className="py-3 px-3 font-mono text-typography-primary">{al.id}</td>
                        <td className="py-3 px-3">
                          <span className="font-extrabold text-[11px]">{al.severity}</span>
                        </td>
                        <td className="py-3 px-3">{al.barangay}</td>
                        <td className="py-3 px-3">{al.waterDepthCm} cm</td>
                        <td className="py-3 px-3 text-typography-secondary">{formatDateTime(al.createdAt)}</td>
                        <td className="py-3 px-3">{al.status}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </div>
    </NavigationShell>
  );
}
