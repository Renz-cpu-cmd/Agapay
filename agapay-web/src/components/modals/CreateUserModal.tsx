'use client';

import React, { useState } from 'react';
import { UserRole } from '@/models/user';
import { useDashboard } from '@/context/DashboardContext';
import { UserPlus, X } from 'lucide-react';

interface CreateUserModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function CreateUserModal({ isOpen, onClose }: CreateUserModalProps) {
  const { createUser } = useDashboard();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [role, setRole] = useState<UserRole>('Officer');
  const [barangay, setBarangay] = useState('Brgy. San Nicolas');
  const [phone, setPhone] = useState('+63 917 ');
  const [isLoading, setIsLoading] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !email) return;

    setIsLoading(true);
    try {
      await createUser({ name, email, role, barangay, phone });
      onClose();
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-border-light animate-in fade-in zoom-in-95 duration-150">
        <div className="flex items-start justify-between pb-4 border-b border-border-light">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-brand-secondaryLight text-brand-primary">
              <UserPlus size={22} />
            </div>
            <div>
              <h3 className="text-lg font-black text-typography-primary">Register New Officer / Responder</h3>
              <p className="text-xs text-typography-secondary">Grant access to AGAPAY Emergency Command System</p>
            </div>
          </div>
          <button onClick={onClose} className="text-typography-muted hover:text-typography-primary p-1">
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="mt-4 space-y-3.5">
          <div>
            <label className="block text-xs font-bold text-typography-secondary uppercase mb-1">
              Full Name & Title
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Officer Juan Dela Cruz"
              className="w-full text-xs font-semibold p-2.5 rounded-xl border border-border-light bg-surface-secondary focus:bg-white focus:ring-2 focus:ring-brand-secondary outline-none"
              required
            />
          </div>

          <div>
            <label className="block text-xs font-bold text-typography-secondary uppercase mb-1">
              Government / Official Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="e.g. j.delacruz@lgu.drrmc.gov.ph"
              className="w-full text-xs font-semibold p-2.5 rounded-xl border border-border-light bg-surface-secondary focus:bg-white focus:ring-2 focus:ring-brand-secondary outline-none"
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-bold text-typography-secondary uppercase mb-1">Role</label>
              <select
                value={role}
                onChange={(e) => setRole(e.target.value as UserRole)}
                className="w-full text-xs font-semibold p-2.5 rounded-xl border border-border-light bg-surface-secondary focus:bg-white focus:ring-2 focus:ring-brand-secondary outline-none"
              >
                <option value="Officer">Officer</option>
                <option value="Responder">Responder</option>
                <option value="Admin">Admin</option>
                <option value="Resident">Resident</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-bold text-typography-secondary uppercase mb-1">
                Assigned Barangay
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
              Mobile Contact Number
            </label>
            <input
              type="text"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              className="w-full text-xs font-semibold p-2.5 rounded-xl border border-border-light bg-surface-secondary focus:bg-white focus:ring-2 focus:ring-brand-secondary outline-none"
              required
            />
          </div>

          <div className="pt-3 flex items-center justify-end gap-3 border-t border-border-light">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-xs font-bold text-typography-secondary bg-surface-secondary hover:bg-border-light rounded-xl"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isLoading}
              className="px-5 py-2 text-xs font-extrabold text-white bg-brand-primary hover:bg-brand-primaryDark rounded-xl shadow-md"
            >
              {isLoading ? 'Creating...' : 'Register User'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
