'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  Radio,
  BellRing,
  Siren,
  LineChart,
  FileText,
  Users,
  Activity,
  Settings,
  ShieldAlert,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { useDashboard } from '@/context/DashboardContext';

interface SidebarProps {
  collapsed: boolean;
  onToggleCollapse: () => void;
}

export function Sidebar({ collapsed, onToggleCollapse }: SidebarProps) {
  const pathname = usePathname();
  const { metrics } = useDashboard();

  const navItems = [
    {
      name: 'Dashboard',
      href: '/dashboard',
      icon: LayoutDashboard,
    },
    {
      name: 'Stations',
      href: '/stations',
      icon: Radio,
    },
    {
      name: 'Alerts',
      href: '/alerts',
      icon: BellRing,
      badge: metrics.activeAlertsCount > 0 ? metrics.activeAlertsCount : undefined,
      badgeColor: 'bg-alert-warning text-white',
    },
    {
      name: 'SOS Beacons',
      href: '/sos',
      icon: Siren,
      badge: metrics.activeSOSCount > 0 ? metrics.activeSOSCount : undefined,
      badgeColor: 'bg-alert-sos text-white animate-pulse',
    },
    {
      name: 'Analytics',
      href: '/analytics',
      icon: LineChart,
    },
    {
      name: 'Reports',
      href: '/reports',
      icon: FileText,
    },
    {
      name: 'Users',
      href: '/users',
      icon: Users,
    },
    {
      name: 'System Health',
      href: '/system-health',
      icon: Activity,
    },
    {
      name: 'Settings',
      href: '/settings',
      icon: Settings,
    },
  ];

  return (
    <aside
      className={`fixed left-0 top-0 bottom-0 z-40 bg-white border-r border-border-light flex flex-col transition-all duration-300 ${
        collapsed ? 'w-20' : 'w-64'
      }`}
    >
      {/* Brand Header */}
      <div className="h-16 flex items-center justify-between px-4 border-b border-border-light">
        <Link href="/dashboard" className="flex items-center gap-3 overflow-hidden">
          <div className="w-10 h-10 rounded-xl bg-brand-primary flex items-center justify-center text-white font-black text-lg shadow-md shrink-0">
            ⚡
          </div>
          {!collapsed && (
            <div className="flex flex-col">
              <span className="font-black text-lg text-brand-primary tracking-wider leading-none">
                AGAPAY
              </span>
              <span className="text-[10px] font-extrabold text-typography-secondary tracking-tight uppercase mt-0.5">
                Disaster Command
              </span>
            </div>
          )}
        </Link>
        <button
          onClick={onToggleCollapse}
          className="text-typography-secondary hover:text-brand-primary p-1.5 rounded-lg hover:bg-surface-secondary transition-colors"
          title={collapsed ? 'Expand Sidebar' : 'Collapse Sidebar'}
        >
          {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
        </button>
      </div>

      {/* Navigation Links */}
      <div className="flex-1 py-4 px-3 space-y-1 overflow-y-auto">
        {navItems.map((item) => {
          const isActive = pathname === item.href || (item.href !== '/dashboard' && pathname?.startsWith(item.href));
          const Icon = item.icon;

          return (
            <Link
              key={item.name}
              href={item.href}
              className={`flex items-center gap-3 px-3.5 py-2.5 rounded-xl font-bold text-sm transition-all group ${
                isActive
                  ? 'bg-brand-primary text-white shadow-md shadow-brand-primary/20'
                  : 'text-typography-secondary hover:text-brand-primary hover:bg-surface-secondary'
              }`}
            >
              <Icon
                size={20}
                className={isActive ? 'text-white' : 'text-typography-secondary group-hover:text-brand-primary'}
              />
              {!collapsed && (
                <div className="flex-1 flex items-center justify-between">
                  <span>{item.name}</span>
                  {item.badge !== undefined && (
                    <span
                      className={`text-[10px] font-black px-2 py-0.5 rounded-full ${item.badgeColor}`}
                    >
                      {item.badge}
                    </span>
                  )}
                </div>
              )}
            </Link>
          );
        })}
      </div>

      {/* Footer / LGU Jurisdiction Pill */}
      {!collapsed && (
        <div className="p-4 border-t border-border-light bg-surface-secondary/50">
          <div className="bg-white p-3 rounded-xl border border-border-light shadow-sm text-xs">
            <p className="text-[10px] font-bold text-typography-muted uppercase">Jurisdiction</p>
            <p className="font-extrabold text-typography-primary mt-0.5">Bulacan DRRM Central</p>
            <div className="flex items-center gap-1.5 mt-2 text-[10px] font-bold text-alert-normal">
              <span className="w-2 h-2 rounded-full bg-alert-normal animate-pulse"></span>
              <span>5 ESP32 Stations Live</span>
            </div>
          </div>
        </div>
      )}
    </aside>
  );
}
