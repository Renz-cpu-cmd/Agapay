'use client';

import React, { useState } from 'react';
import { NavigationShell } from '@/components/layout/NavigationShell';
import { useDashboard } from '@/context/DashboardContext';
import { LeafletMapWrapper } from '@/components/maps/LeafletMapWrapper';
import { SOSBeacon } from '@/models/sos';
import {
  Siren,
  Phone,
  MapPin,
  Clock,
  ShieldAlert,
  CheckCircle,
  Navigation,
  LifeBuoy,
} from 'lucide-react';
import { formatRelativeTime, formatCoordinates } from '@/lib/formatters';

export default function SOSBeaconsPage() {
  const { sosBeacons, stations, acknowledgeSOS, resolveSOS, metrics } = useDashboard();
  const [selectedBeacon, setSelectedBeacon] = useState<SOSBeacon | null>(null);
  const [dispatchTeamName, setDispatchTeamName] = useState('BDRRMC Rescue Boat Alpha');
  const [isDispatchModalOpen, setIsDispatchModalOpen] = useState(false);
  const [activeSOSForModal, setActiveSOSForModal] = useState<SOSBeacon | null>(null);

  const activeBeacons = sosBeacons.filter((b) => b.status !== 'Resolved');
  const resolvedBeacons = sosBeacons.filter((b) => b.status === 'Resolved');

  const openDispatchModal = (beacon: SOSBeacon) => {
    setActiveSOSForModal(beacon);
    setIsDispatchModalOpen(true);
  };

  const handleConfirmDispatch = async () => {
    if (!activeSOSForModal) return;
    await acknowledgeSOS(activeSOSForModal.id, dispatchTeamName);
    setIsDispatchModalOpen(false);
  };

  return (
    <NavigationShell>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-black text-typography-primary tracking-tight">
                Emergency SOS Incident Command
              </h1>
              {metrics.activeSOSCount > 0 && (
                <span className="px-2.5 py-0.5 rounded-full text-xs font-black bg-alert-sos text-white animate-pulse">
                  {metrics.activeSOSCount} Active Beacon{metrics.activeSOSCount > 1 ? 's' : ''}
                </span>
              )}
            </div>
            <p className="text-xs font-semibold text-typography-secondary mt-0.5">
              Live resident GPS distress beacons transmitted from the AGAPAY mobile app
            </p>
          </div>
        </div>

        {/* Map & SOS Triage Split View */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Tactical Map (7 cols) */}
          <div className="lg:col-span-7 flex flex-col space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-black text-typography-primary uppercase tracking-wider flex items-center gap-2">
                <LifeBuoy size={18} className="text-alert-sos" />
                <span>Tactical Rescue Map</span>
              </h3>
              <span className="text-xs text-typography-muted">
                Showing live GPS distress coordinates
              </span>
            </div>

            <LeafletMapWrapper
              stations={stations}
              sosBeacons={sosBeacons}
              height="480px"
            />
          </div>

          {/* Active Distress Incidents Queue (5 cols) */}
          <div className="lg:col-span-5 flex flex-col space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-black text-typography-primary uppercase tracking-wider">
                Active SOS Queue ({activeBeacons.length})
              </h3>
              <span className="text-xs text-typography-muted">Priority Dispatch</span>
            </div>

            <div className="space-y-3 max-h-[480px] overflow-y-auto pr-1">
              {activeBeacons.length === 0 ? (
                <div className="p-12 text-center bg-white rounded-xl border border-border-light text-typography-muted text-xs">
                  <CheckCircle size={32} className="mx-auto text-alert-normal mb-2" />
                  <p className="font-bold text-typography-primary">All SOS Incidents Resolved</p>
                  <p className="mt-1">No pending resident emergency broadcasts.</p>
                </div>
              ) : (
                activeBeacons.map((beacon) => {
                  const isActive = beacon.status === 'Active';
                  return (
                    <div
                      key={beacon.id}
                      className={`p-4 rounded-2xl border transition-all ${
                        isActive
                          ? 'bg-rose-50/50 border-alert-sos/60 shadow-md shadow-rose-100'
                          : 'bg-white border-border-light shadow-card'
                      }`}
                    >
                      <div className="flex items-start justify-between">
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-black text-alert-sos uppercase tracking-wider font-mono">
                              {beacon.id}
                            </span>
                            <span
                              className={`px-2 py-0.5 rounded-full text-[10px] font-black ${
                                isActive
                                  ? 'bg-alert-sos text-white animate-pulse'
                                  : 'bg-blue-100 text-blue-800'
                              }`}
                            >
                              {beacon.status}
                            </span>
                          </div>
                          <h4 className="text-base font-black text-typography-primary mt-1">
                            {beacon.residentName}
                          </h4>
                        </div>
                        <span className="text-[11px] font-bold text-typography-muted flex items-center gap-1">
                          <Clock size={12} />
                          {formatRelativeTime(beacon.createdAt)}
                        </span>
                      </div>

                      {/* Message */}
                      <p className="text-xs font-semibold text-typography-primary bg-white/90 p-2.5 rounded-xl border border-border-light/80 mt-2.5 leading-relaxed">
                        &quot;{beacon.message}&quot;
                      </p>

                      {/* Metadata */}
                      <div className="grid grid-cols-2 gap-2 mt-3 text-[11px] text-typography-secondary font-medium">
                        <div className="flex items-center gap-1.5">
                          <Phone size={13} className="text-brand-secondary" />
                          <span>{beacon.phone}</span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <MapPin size={13} className="text-alert-sos" />
                          <span>{beacon.barangay}</span>
                        </div>
                      </div>

                      {beacon.responderTeam && (
                        <div className="mt-2.5 p-2 rounded-lg bg-blue-50 text-blue-900 border border-blue-200 text-xs font-bold flex items-center justify-between">
                          <span>Team: {beacon.responderTeam}</span>
                          <span className="text-[10px] text-blue-700">Dispatched</span>
                        </div>
                      )}

                      {/* Actions */}
                      <div className="mt-3.5 pt-2.5 border-t border-border-light flex items-center justify-end gap-2">
                        {beacon.status === 'Active' ? (
                          <button
                            onClick={() => openDispatchModal(beacon)}
                            className="px-3.5 py-1.5 bg-alert-sos hover:bg-rose-700 text-white rounded-xl text-xs font-black shadow-sm flex items-center gap-1.5"
                          >
                            <Navigation size={13} />
                            <span>Dispatch Rescue Unit</span>
                          </button>
                        ) : (
                          <button
                            onClick={() => resolveSOS(beacon.id)}
                            className="px-3.5 py-1.5 bg-alert-normal hover:bg-emerald-700 text-white rounded-xl text-xs font-black shadow-sm flex items-center gap-1.5"
                          >
                            <CheckCircle size={13} />
                            <span>Mark Rescued & Safe</span>
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>

        {/* Resolved SOS Incident History Log */}
        <div className="bg-white rounded-2xl border border-border-light shadow-card p-5">
          <h3 className="text-sm font-black text-typography-primary uppercase tracking-wider mb-3">
            Resolved Incident History ({resolvedBeacons.length})
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-semibold">
              <thead className="bg-surface-secondary text-typography-secondary text-[10px] uppercase font-bold">
                <tr>
                  <th className="py-2.5 px-4">Beacon ID</th>
                  <th className="py-2.5 px-4">Resident</th>
                  <th className="py-2.5 px-4">Barangay</th>
                  <th className="py-2.5 px-4">Distress Details</th>
                  <th className="py-2.5 px-4">Resolved By</th>
                  <th className="py-2.5 px-4 text-right">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-light">
                {resolvedBeacons.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-6 text-center text-typography-muted">
                      No resolved records in current session.
                    </td>
                  </tr>
                ) : (
                  resolvedBeacons.map((b) => (
                    <tr key={b.id} className="hover:bg-surface-secondary/40">
                      <td className="py-3 px-4 font-mono font-bold text-typography-primary">{b.id}</td>
                      <td className="py-3 px-4">{b.residentName}</td>
                      <td className="py-3 px-4">{b.barangay}</td>
                      <td className="py-3 px-4 max-w-xs truncate text-typography-secondary">{b.message}</td>
                      <td className="py-3 px-4 text-typography-secondary">{b.resolvedBy || 'Officer'}</td>
                      <td className="py-3 px-4 text-right">
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-100 text-slate-700">
                          Resolved Safe
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Dispatch Confirmation Modal */}
      {isDispatchModalOpen && activeSOSForModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-border-light space-y-4">
            <h3 className="text-lg font-black text-typography-primary">
              Assign & Dispatch Rescue Team
            </h3>
            <p className="text-xs text-typography-secondary">
              Resident: <strong>{activeSOSForModal.residentName}</strong> ({activeSOSForModal.barangay})
            </p>

            <div>
              <label className="block text-xs font-bold text-typography-secondary uppercase mb-1">
                Select Responding Unit
              </label>
              <select
                value={dispatchTeamName}
                onChange={(e) => setDispatchTeamName(e.target.value)}
                className="w-full text-xs font-bold p-2.5 rounded-xl border border-border-light bg-surface-secondary outline-none"
              >
                <option value="BDRRMC Rescue Boat Alpha">BDRRMC Rescue Boat Alpha</option>
                <option value="BDRRMC Quick Inflatable #2">BDRRMC Quick Inflatable #2</option>
                <option value="Red Cross Disaster Response Team">Red Cross Disaster Response Team</option>
                <option value="Philippine Coast Guard Auxiliary Unit">Philippine Coast Guard Auxiliary Unit</option>
              </select>
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setIsDispatchModalOpen(false)}
                className="px-4 py-2 text-xs font-bold text-typography-secondary"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmDispatch}
                className="px-5 py-2 text-xs font-black text-white bg-alert-sos hover:bg-rose-700 rounded-xl shadow-md"
              >
                Confirm Dispatch Order
              </button>
            </div>
          </div>
        </div>
      )}
    </NavigationShell>
  );
}
