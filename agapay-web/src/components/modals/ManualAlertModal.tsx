'use client';

import React, { useState } from 'react';
import { AlertLevel, ALERT_CONFIGS } from '@/constants/theme';
import { useDashboard } from '@/context/DashboardContext';
import { AlertTriangle, X, Radio } from 'lucide-react';

interface ManualAlertModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function ManualAlertModal({ isOpen, onClose }: ManualAlertModalProps) {
  const { createManualAlert, stations } = useDashboard();
  const [severity, setSeverity] = useState<AlertLevel>('WARNING');
  const [stationName, setStationName] = useState<string>(stations[0]?.name || 'Central Command Sector');
  const [barangay, setBarangay] = useState<string>(stations[0]?.barangay || 'Brgy. San Nicolas');
  const [message, setMessage] = useState<string>('');
  const [recommendedAction, setRecommendedAction] = useState<string>('');
  const [showConfirm, setShowConfirm] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  if (!isOpen) return null;

  const handleStationChange = (name: string) => {
    setStationName(name);
    const matched = stations.find((s) => s.name === name);
    if (matched) {
      setBarangay(matched.barangay);
    }
  };

  const handleProceedToConfirm = (e: React.FormEvent) => {
    e.preventDefault();
    if (!message || !recommendedAction) return;
    setShowConfirm(true);
  };

  const handleExecuteBroadcast = async () => {
    setIsSubmitting(true);
    try {
      await createManualAlert({
        severity,
        barangay,
        stationName,
        message,
        recommendedAction,
      });
      setShowConfirm(false);
      onClose();
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-border-light animate-in fade-in zoom-in-95 duration-150">
        {!showConfirm ? (
          <div>
            <div className="flex items-start justify-between pb-4 border-b border-border-light">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-xl bg-alert-warningBg text-alert-warning">
                  <Radio size={22} />
                </div>
                <div>
                  <h3 className="text-lg font-black text-typography-primary">Broadcast Manual Emergency Alert</h3>
                  <p className="text-xs text-typography-secondary">
                    Transmit high-priority flood warning across citizen mobile apps
                  </p>
                </div>
              </div>
              <button
                onClick={onClose}
                className="text-typography-muted hover:text-typography-primary p-1 rounded-lg transition-colors"
              >
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleProceedToConfirm} className="mt-4 space-y-4">
              <div>
                <label className="block text-xs font-bold text-typography-secondary uppercase mb-1">
                  Alert Severity Tier
                </label>
                <div className="grid grid-cols-4 gap-2">
                  {(['NORMAL', 'ADVISORY', 'WARNING', 'EVACUATE'] as AlertLevel[]).map((lvl) => {
                    const cfg = ALERT_CONFIGS[lvl];
                    const isSelected = severity === lvl;
                    return (
                      <button
                        type="button"
                        key={lvl}
                        onClick={() => setSeverity(lvl)}
                        className={`p-2.5 rounded-xl border text-xs font-black transition-all ${
                          isSelected
                            ? 'ring-2 ring-offset-1'
                            : 'opacity-70 hover:opacity-100 bg-surface-secondary'
                        }`}
                        style={{
                          backgroundColor: isSelected ? cfg.bgColor : undefined,
                          color: cfg.textColor,
                          borderColor: cfg.borderColor,
                          outlineColor: cfg.color,
                        }}
                      >
                        {cfg.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold text-typography-secondary uppercase mb-1">
                    Sensor Station / Sector
                  </label>
                  <select
                    value={stationName}
                    onChange={(e) => handleStationChange(e.target.value)}
                    className="w-full text-xs font-semibold p-2.5 rounded-xl border border-border-light bg-surface-secondary focus:bg-white focus:ring-2 focus:ring-brand-secondary outline-none"
                  >
                    {stations.map((st) => (
                      <option key={st.id} value={st.name}>
                        {st.name}
                      </option>
                    ))}
                    <option value="Sector-Wide General Broadcast">Sector-Wide General Broadcast</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-bold text-typography-secondary uppercase mb-1">
                    Target Barangay
                  </label>
                  <input
                    type="text"
                    value={barangay}
                    onChange={(e) => setBarangay(e.target.value)}
                    className="w-full text-xs font-semibold p-2.5 rounded-xl border border-border-light bg-surface-secondary focus:bg-white focus:ring-2 focus:ring-brand-secondary outline-none"
                    required
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-typography-secondary uppercase mb-1">
                  Alert Bulletin Message
                </label>
                <textarea
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  placeholder="e.g. Flash flood warning issued for low-lying areas. River gates opening upstream."
                  rows={3}
                  className="w-full text-xs font-medium p-2.5 rounded-xl border border-border-light bg-surface-secondary focus:bg-white focus:ring-2 focus:ring-brand-secondary outline-none"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-typography-secondary uppercase mb-1">
                  Official Recommended Action
                </label>
                <input
                  type="text"
                  value={recommendedAction}
                  onChange={(e) => setRecommendedAction(e.target.value)}
                  placeholder="e.g. Evacuate immediately to San Nicolas Elementary School Gym."
                  className="w-full text-xs font-medium p-2.5 rounded-xl border border-border-light bg-surface-secondary focus:bg-white focus:ring-2 focus:ring-brand-secondary outline-none"
                  required
                />
              </div>

              <div className="pt-3 flex items-center justify-end gap-3 border-t border-border-light">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2 text-xs font-bold text-typography-secondary bg-surface-secondary hover:bg-border-light rounded-xl transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 text-xs font-extrabold text-white bg-brand-primary hover:bg-brand-primaryDark rounded-xl shadow-md transition-colors"
                >
                  Review & Broadcast &rarr;
                </button>
              </div>
            </form>
          </div>
        ) : (
          /* Confirmation Step */
          <div className="space-y-4">
            <div className="flex items-center gap-3">
              <div className="p-3 rounded-full bg-alert-evacuateBg text-alert-evacuate">
                <AlertTriangle size={24} />
              </div>
              <div>
                <h3 className="text-lg font-black text-typography-primary">Confirm Emergency Broadcast?</h3>
                <p className="text-xs text-typography-secondary">
                  This will trigger instantaneous push notifications to all registered residents.
                </p>
              </div>
            </div>

            <div className="bg-surface-secondary p-4 rounded-xl border border-border-light space-y-2 text-xs">
              <p>
                <strong>Tier:</strong> <span className="font-extrabold">{severity}</span>
              </p>
              <p>
                <strong>Target Area:</strong> {barangay} ({stationName})
              </p>
              <p>
                <strong>Message:</strong> {message}
              </p>
              <p>
                <strong>Action:</strong> {recommendedAction}
              </p>
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setShowConfirm(false)}
                className="px-4 py-2 text-xs font-bold text-typography-secondary bg-surface-secondary hover:bg-border-light rounded-xl transition-colors"
              >
                Back to Edit
              </button>
              <button
                type="button"
                onClick={handleExecuteBroadcast}
                disabled={isSubmitting}
                className="px-5 py-2 text-xs font-black text-white bg-alert-evacuate hover:bg-red-700 rounded-xl shadow-lg transition-transform active:scale-95 flex items-center gap-2"
              >
                {isSubmitting ? 'Transmitting...' : 'CONFIRM & TRANSMIT NOW'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
