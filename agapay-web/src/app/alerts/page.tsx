'use client';

import React, { useState } from 'react';
import { NavigationShell } from '@/components/layout/NavigationShell';
import { useDashboard } from '@/context/DashboardContext';
import { StatusBadge } from '@/components/common/StatusBadge';
import { AlertLevel } from '@/constants/theme';
import { ManualAlertModal } from '@/components/modals/ManualAlertModal';
import {
  BellRing,
  Radio,
  CheckCircle2,
  AlertTriangle,
  Search,
  Filter,
  ArrowUpDown,
  Share2,
} from 'lucide-react';
import { formatRelativeTime, formatDateTime, formatWaterLevel } from '@/lib/formatters';

export default function AlertManagementPage() {
  const { alerts, resolveAlert, acknowledgeAlert } = useDashboard();
  const [searchQuery, setSearchQuery] = useState('');
  const [severityFilter, setSeverityFilter] = useState<string>('ALL');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [isManualModalOpen, setIsManualModalOpen] = useState(false);

  const filteredAlerts = alerts.filter((a) => {
    const matchesSearch =
      a.stationName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      a.barangay.toLowerCase().includes(searchQuery.toLowerCase()) ||
      a.message.toLowerCase().includes(searchQuery.toLowerCase());

    const matchesSeverity = severityFilter === 'ALL' || a.severity === severityFilter;
    const matchesStatus = statusFilter === 'ALL' || a.status === statusFilter;

    return matchesSearch && matchesSeverity && matchesStatus;
  });

  return (
    <NavigationShell>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-black text-typography-primary tracking-tight">
              Flood Alert Management & Broadcast
            </h1>
            <p className="text-xs font-semibold text-typography-secondary mt-0.5">
              Triage automated threshold breaches and dispatch public safety bulletins to residents
            </p>
          </div>

          <button
            onClick={() => setIsManualModalOpen(true)}
            className="flex items-center gap-2 px-4 py-2 bg-alert-warning hover:bg-orange-600 text-white rounded-xl text-xs font-black shadow-md transition-all active:scale-95 self-start md:self-auto"
          >
            <Radio size={16} className="animate-pulse" />
            <span>Create Manual Broadcast Alert</span>
          </button>
        </div>

        {/* Filter Bar */}
        <div className="bg-white p-4 rounded-2xl border border-border-light shadow-card flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="relative w-full md:w-80">
            <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-typography-muted" />
            <input
              type="text"
              placeholder="Search alert, barangay, or message..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full text-xs font-semibold pl-10 pr-4 py-2 rounded-xl border border-border-light bg-surface-secondary focus:bg-white focus:ring-2 focus:ring-brand-secondary outline-none"
            />
          </div>

          <div className="flex flex-wrap items-center gap-3 w-full md:w-auto">
            {/* Severity Filter */}
            <div className="flex items-center gap-1.5 text-xs">
              <span className="font-bold text-typography-secondary">Severity:</span>
              <select
                value={severityFilter}
                onChange={(e) => setSeverityFilter(e.target.value)}
                className="text-xs font-bold p-2 rounded-xl border border-border-light bg-surface-secondary outline-none cursor-pointer"
              >
                <option value="ALL">All Severity Tiers</option>
                <option value="EVACUATE">Evacuate</option>
                <option value="WARNING">Warning</option>
                <option value="ADVISORY">Advisory</option>
                <option value="NORMAL">Normal</option>
              </select>
            </div>

            {/* Status Filter */}
            <div className="flex items-center gap-1.5 text-xs">
              <span className="font-bold text-typography-secondary">Status:</span>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="text-xs font-bold p-2 rounded-xl border border-border-light bg-surface-secondary outline-none cursor-pointer"
              >
                <option value="ALL">All Statuses</option>
                <option value="Active">Active Only</option>
                <option value="Acknowledged">Acknowledged</option>
                <option value="Resolved">Resolved</option>
              </select>
            </div>
          </div>
        </div>

        {/* Alerts Table */}
        <div className="bg-white rounded-2xl border border-border-light shadow-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-surface-secondary/70 border-b border-border-light text-[11px] font-black text-typography-secondary uppercase tracking-wider">
                  <th className="py-3.5 px-4">Severity Tier</th>
                  <th className="py-3.5 px-4">Station & Barangay</th>
                  <th className="py-3.5 px-4">Water Depth</th>
                  <th className="py-3.5 px-4">Alert Message & Directive</th>
                  <th className="py-3.5 px-4">Timestamp</th>
                  <th className="py-3.5 px-4">Status</th>
                  <th className="py-3.5 px-4 text-right">Officer Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-light text-xs font-semibold">
                {filteredAlerts.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="py-12 text-center text-typography-muted">
                      No alert bulletins found matching current filters.
                    </td>
                  </tr>
                ) : (
                  filteredAlerts.map((alert) => {
                    const isResolved = alert.status === 'Resolved';
                    const isEvacuate = alert.severity === 'EVACUATE';

                    return (
                      <tr
                        key={alert.id}
                        className={`transition-colors ${
                          !isResolved && isEvacuate
                            ? 'bg-alert-evacuateBg/20 hover:bg-alert-evacuateBg/40'
                            : 'hover:bg-surface-secondary/50'
                        }`}
                      >
                        <td className="py-4 px-4">
                          <StatusBadge level={alert.severity} size="sm" />
                          {alert.isManualBroadcast && (
                            <span className="block text-[9px] font-black text-blue-700 mt-1 uppercase">
                              Manual Broadcast
                            </span>
                          )}
                        </td>

                        <td className="py-4 px-4">
                          <strong className="text-typography-primary block">{alert.stationName}</strong>
                          <span className="text-typography-secondary text-[11px]">{alert.barangay}</span>
                        </td>

                        <td className="py-4 px-4">
                          <div className="font-black text-sm text-typography-primary">
                            {formatWaterLevel(alert.waterDepthCm)}
                          </div>
                          <span className="text-[10px] text-typography-muted">
                            Threshold: {alert.thresholdCm} cm
                          </span>
                        </td>

                        <td className="py-4 px-4 max-w-xs">
                          <p className="font-bold text-typography-primary text-xs leading-snug">
                            {alert.message}
                          </p>
                          <p className="text-[11px] text-brand-primary font-bold mt-1 bg-surface-secondary p-1.5 rounded-lg border border-border-light">
                            <strong>Action:</strong> {alert.recommendedAction}
                          </p>
                        </td>

                        <td className="py-4 px-4 text-typography-secondary text-[11px]">
                          <span className="font-bold text-typography-primary block">
                            {formatRelativeTime(alert.createdAt)}
                          </span>
                          <span>{formatDateTime(alert.createdAt)}</span>
                        </td>

                        <td className="py-4 px-4">
                          <span
                            className={`inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-extrabold ${
                              alert.status === 'Active'
                                ? 'bg-rose-50 text-rose-800 border border-rose-200'
                                : alert.status === 'Acknowledged'
                                ? 'bg-amber-50 text-amber-800 border border-amber-200'
                                : 'bg-slate-100 text-slate-700 border border-slate-200'
                            }`}
                          >
                            {alert.status}
                          </span>
                        </td>

                        <td className="py-4 px-4 text-right">
                          {!isResolved ? (
                            <div className="flex items-center justify-end gap-2">
                              {alert.status === 'Active' && (
                                <button
                                  onClick={() => acknowledgeAlert(alert.id)}
                                  className="px-3 py-1 bg-surface-secondary hover:bg-slate-200 text-typography-primary text-xs font-bold rounded-lg transition-colors"
                                >
                                  Acknowledge
                                </button>
                              )}
                              <button
                                onClick={() => resolveAlert(alert.id)}
                                className="px-3 py-1 bg-brand-primary hover:bg-brand-primaryDark text-white text-xs font-extrabold rounded-lg shadow-sm transition-colors"
                              >
                                Resolve
                              </button>
                            </div>
                          ) : (
                            <span className="text-[11px] text-typography-muted font-medium">
                              Resolved by {alert.resolvedBy || 'Officer'}
                            </span>
                          )}
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

      {/* Manual Alert Broadcast Modal */}
      <ManualAlertModal isOpen={isManualModalOpen} onClose={() => setIsManualModalOpen(false)} />
    </NavigationShell>
  );
}
