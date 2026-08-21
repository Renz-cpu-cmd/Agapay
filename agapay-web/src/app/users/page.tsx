'use client';

import React, { useState } from 'react';
import { NavigationShell } from '@/components/layout/NavigationShell';
import { useDashboard } from '@/context/DashboardContext';
import { User, UserRole } from '@/models/user';
import { CreateUserModal } from '@/components/modals/CreateUserModal';
import { ConfirmDialog } from '@/components/common/ConfirmDialog';
import {
  Users,
  UserPlus,
  Shield,
  ShieldCheck,
  Search,
  CheckCircle2,
  XCircle,
  MoreVertical,
} from 'lucide-react';

export default function UserManagementPage() {
  const { users, toggleUserStatus } = useDashboard();
  const [searchQuery, setSearchQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState<string>('ALL');
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [confirmToggleUser, setConfirmToggleUser] = useState<User | null>(null);

  const filteredUsers = users.filter((u) => {
    const matchesSearch =
      u.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      u.email.toLowerCase().includes(searchQuery.toLowerCase()) ||
      u.barangay.toLowerCase().includes(searchQuery.toLowerCase());

    const matchesRole = roleFilter === 'ALL' || u.role === roleFilter;
    return matchesSearch && matchesRole;
  });

  const handleConfirmToggleStatus = async () => {
    if (!confirmToggleUser) return;
    await toggleUserStatus(confirmToggleUser.id);
    setConfirmToggleUser(null);
  };

  return (
    <NavigationShell>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-black text-typography-primary tracking-tight">
              User & Officer Access Management
            </h1>
            <p className="text-xs font-semibold text-typography-secondary mt-0.5">
              Role-based access control for LGU disaster dispatchers and emergency responders
            </p>
          </div>

          <button
            onClick={() => setIsCreateModalOpen(true)}
            className="flex items-center gap-2 px-4 py-2 bg-brand-primary hover:bg-brand-primaryDark text-white rounded-xl text-xs font-black shadow-md transition-all active:scale-95"
          >
            <UserPlus size={16} />
            <span>Register New Officer / Responder</span>
          </button>
        </div>

        {/* Filters */}
        <div className="bg-white p-4 rounded-2xl border border-border-light shadow-card flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="relative w-full md:w-80">
            <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-typography-muted" />
            <input
              type="text"
              placeholder="Search user by name, email, or barangay..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full text-xs font-semibold pl-10 pr-4 py-2 rounded-xl border border-border-light bg-surface-secondary focus:bg-white focus:ring-2 focus:ring-brand-secondary outline-none"
            />
          </div>

          <div className="flex items-center gap-2 text-xs">
            <span className="font-bold text-typography-secondary">Role Filter:</span>
            <select
              value={roleFilter}
              onChange={(e) => setRoleFilter(e.target.value)}
              className="text-xs font-bold p-2 rounded-xl border border-border-light bg-surface-secondary outline-none cursor-pointer"
            >
              <option value="ALL">All Roles</option>
              <option value="Admin">Admin</option>
              <option value="Officer">Officer</option>
              <option value="Responder">Responder</option>
              <option value="Resident">Resident</option>
            </select>
          </div>
        </div>

        {/* Users Table */}
        <div className="bg-white rounded-2xl border border-border-light shadow-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs font-semibold">
              <thead>
                <tr className="bg-surface-secondary/70 border-b border-border-light text-[11px] font-black text-typography-secondary uppercase tracking-wider">
                  <th className="py-3.5 px-4">Officer Name & Badge</th>
                  <th className="py-3.5 px-4">Official Email</th>
                  <th className="py-3.5 px-4">Role</th>
                  <th className="py-3.5 px-4">Barangay Zone</th>
                  <th className="py-3.5 px-4">Phone Number</th>
                  <th className="py-3.5 px-4">Account Status</th>
                  <th className="py-3.5 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-light">
                {filteredUsers.map((user) => {
                  const isActive = user.status === 'Active';
                  return (
                    <tr key={user.id} className="hover:bg-surface-secondary/50 transition-colors">
                      <td className="py-3.5 px-4">
                        <div className="flex items-center gap-2.5">
                          <div className="w-8 h-8 rounded-lg bg-brand-primary flex items-center justify-center text-white font-extrabold text-xs">
                            {user.name[0]}
                          </div>
                          <div>
                            <span className="font-extrabold text-typography-primary block">
                              {user.name}
                            </span>
                            <span className="text-[10px] text-typography-muted font-mono">
                              {user.badgeNumber || user.id}
                            </span>
                          </div>
                        </div>
                      </td>

                      <td className="py-3.5 px-4 text-typography-secondary">{user.email}</td>

                      <td className="py-3.5 px-4">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-black uppercase ${
                            user.role === 'Admin'
                              ? 'bg-purple-100 text-purple-800'
                              : user.role === 'Officer'
                              ? 'bg-blue-100 text-blue-800'
                              : user.role === 'Responder'
                              ? 'bg-amber-100 text-amber-800'
                              : 'bg-slate-100 text-slate-700'
                          }`}
                        >
                          {user.role}
                        </span>
                      </td>

                      <td className="py-3.5 px-4 text-typography-primary">{user.barangay}</td>

                      <td className="py-3.5 px-4 text-typography-secondary">{user.phone}</td>

                      <td className="py-3.5 px-4">
                        <span
                          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-extrabold ${
                            isActive
                              ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                              : 'bg-slate-100 text-slate-700 border border-slate-200'
                          }`}
                        >
                          <span
                            className={`w-1.5 h-1.5 rounded-full ${
                              isActive ? 'bg-emerald-500' : 'bg-slate-400'
                            }`}
                          ></span>
                          {user.status}
                        </span>
                      </td>

                      <td className="py-3.5 px-4 text-right">
                        <button
                          onClick={() => setConfirmToggleUser(user)}
                          className={`px-3 py-1 text-xs font-bold rounded-lg transition-colors ${
                            isActive
                              ? 'text-alert-evacuate hover:bg-alert-evacuateBg'
                              : 'text-alert-normal hover:bg-alert-normalBg'
                          }`}
                        >
                          {isActive ? 'Deactivate' : 'Activate'}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Create User Modal */}
      <CreateUserModal isOpen={isCreateModalOpen} onClose={() => setIsCreateModalOpen(false)} />

      {/* Deactivate/Activate Confirmation Dialog */}
      <ConfirmDialog
        isOpen={confirmToggleUser !== null}
        title={`${confirmToggleUser?.status === 'Active' ? 'Deactivate' : 'Activate'} User Account?`}
        message={`Are you sure you want to change access permissions for ${confirmToggleUser?.name} (${confirmToggleUser?.role})?`}
        confirmLabel={confirmToggleUser?.status === 'Active' ? 'Deactivate Access' : 'Activate Access'}
        isDanger={confirmToggleUser?.status === 'Active'}
        onConfirm={handleConfirmToggleStatus}
        onCancel={() => setConfirmToggleUser(null)}
      />
    </NavigationShell>
  );
}
