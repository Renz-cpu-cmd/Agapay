'use client';

import React, { useState, ReactNode } from 'react';
import { Sidebar } from './Sidebar';
import { TopHeader } from './TopHeader';
import { useDashboard } from '@/context/DashboardContext';
import { OfflineBanner } from '../common/OfflineBanner';

export function NavigationShell({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const { isOffline, refreshData } = useDashboard();

  return (
    <div className="min-h-screen bg-surface-bg text-typography-primary flex flex-col font-sans">
      <Sidebar collapsed={collapsed} onToggleCollapse={() => setCollapsed(!collapsed)} />

      <div
        className={`flex-1 flex flex-col transition-all duration-300 ${
          collapsed ? 'ml-20' : 'ml-64'
        }`}
      >
        <TopHeader sidebarCollapsed={collapsed} />

        <main className="flex-1 mt-16 p-6 overflow-y-auto">
          {isOffline && (
            <div className="mb-4">
              <OfflineBanner onRetry={refreshData} />
            </div>
          )}
          {children}
        </main>
      </div>
    </div>
  );
}
