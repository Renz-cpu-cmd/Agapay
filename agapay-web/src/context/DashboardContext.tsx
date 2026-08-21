'use client';

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { Station, computeAlertLevel } from '@/models/station';
import { FloodAlert } from '@/models/alert';
import { SOSBeacon } from '@/models/sos';
import { User } from '@/models/user';
import { stationRepository } from '@/repositories/stationRepository';
import { alertRepository } from '@/repositories/alertRepository';
import { sosRepository } from '@/repositories/sosRepository';
import { userRepository } from '@/repositories/userRepository';
import { AlertLevel } from '@/constants/theme';

interface DashboardContextType {
  stations: Station[];
  alerts: FloodAlert[];
  sosBeacons: SOSBeacon[];
  users: User[];
  selectedBarangay: string;
  isOffline: boolean;
  currentUser: {
    name: string;
    role: string;
    badge: string;
    email: string;
  };
  metrics: {
    activeAlertsCount: number;
    criticalStationsCount: number;
    averageWaterLevelCm: number;
    activeSOSCount: number;
  };
  resolveAlert: (id: string) => Promise<void>;
  acknowledgeAlert: (id: string) => Promise<void>;
  createManualAlert: (params: {
    severity: AlertLevel;
    barangay: string;
    stationName: string;
    message: string;
    recommendedAction: string;
  }) => Promise<void>;
  acknowledgeSOS: (id: string, responderTeam: string) => Promise<void>;
  resolveSOS: (id: string) => Promise<void>;
  updateStationThresholds: (
    stationId: string,
    thresholds: { advisory: number; warning: number; evacuate: number }
  ) => Promise<void>;
  createUser: (params: { name: string; email: string; role: any; barangay: string; phone: string }) => Promise<void>;
  toggleUserStatus: (id: string) => Promise<void>;
  setSelectedBarangay: (barangay: string) => void;
  toggleOfflineMode: () => void;
  refreshData: () => Promise<void>;
}

const DashboardContext = createContext<DashboardContextType | undefined>(undefined);

export function DashboardProvider({ children }: { children: ReactNode }) {
  const [stations, setStations] = useState<Station[]>([]);
  const [alerts, setAlerts] = useState<FloodAlert[]>([]);
  const [sosBeacons, setSosBeacons] = useState<SOSBeacon[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [selectedBarangay, setSelectedBarangay] = useState<string>('All Barangays');
  const [isOffline, setIsOffline] = useState<boolean>(false);

  const currentUser = {
    name: 'Cmdr. Antonio Ramos',
    role: 'Lead Disaster Operations Officer',
    badge: 'LGU-DRRM-001',
    email: 'antonio.ramos@lgu.drrmc.gov.ph',
  };

  const loadData = async () => {
    const [st, al, sos, u] = await Promise.all([
      stationRepository.getStations(),
      alertRepository.getAlerts(),
      sosRepository.getBeacons(),
      userRepository.getUsers(),
    ]);
    setStations(st);
    setAlerts(al);
    setSosBeacons(sos);
    setUsers(u);
  };

  useEffect(() => {
    loadData();
  }, []);

  // Simulated live sensor stream ticker (every 10s)
  useEffect(() => {
    if (isOffline) return;

    const interval = setInterval(() => {
      setStations((prev) =>
        prev.map((s) => {
          if (s.status !== 'Online') return s;
          const delta = (Math.random() - 0.48) * 0.8;
          const newDepth = Math.max(10, Math.min(125, s.waterDepthCm + delta));
          const updatedStation: Station = {
            ...s,
            waterDepthCm: parseFloat(newDepth.toFixed(1)),
            lastPing: new Date().toISOString(),
            trend: delta > 0.05 ? 'rising' : delta < -0.05 ? 'falling' : 'stable',
          };
          updatedStation.alertLevel = computeAlertLevel(updatedStation);
          return updatedStation;
        })
      );
    }, 10000);

    return () => clearInterval(interval);
  }, [isOffline]);

  // Computed live metrics
  const activeAlertsCount = alerts.filter((a) => a.status !== 'Resolved').length;
  const criticalStationsCount = stations.filter(
    (s) => s.alertLevel === 'WARNING' || s.alertLevel === 'EVACUATE'
  ).length;
  const averageWaterLevelCm =
    stations.length > 0
      ? Math.round(stations.reduce((acc, s) => acc + s.waterDepthCm, 0) / stations.length)
      : 0;
  const activeSOSCount = sosBeacons.filter((b) => b.status === 'Active' || b.status === 'EnRoute').length;

  const resolveAlert = async (id: string) => {
    const updated = await alertRepository.resolveAlert(id, currentUser.name);
    setAlerts((prev) => prev.map((a) => (a.id === id ? updated : a)));
  };

  const acknowledgeAlert = async (id: string) => {
    const updated = await alertRepository.acknowledgeAlert(id);
    setAlerts((prev) => prev.map((a) => (a.id === id ? updated : a)));
  };

  const createManualAlert = async (params: {
    severity: AlertLevel;
    barangay: string;
    stationName: string;
    message: string;
    recommendedAction: string;
  }) => {
    const created = await alertRepository.createManualAlert({
      ...params,
      broadcastBy: currentUser.name,
    });
    setAlerts((prev) => [created, ...prev]);
  };

  const acknowledgeSOS = async (id: string, responderTeam: string) => {
    const updated = await sosRepository.acknowledgeSOS(id, responderTeam, currentUser.name);
    setSosBeacons((prev) => prev.map((b) => (b.id === id ? updated : b)));
  };

  const resolveSOS = async (id: string) => {
    const updated = await sosRepository.resolveSOS(id, currentUser.name);
    setSosBeacons((prev) => prev.map((b) => (b.id === id ? updated : b)));
  };

  const updateStationThresholds = async (
    stationId: string,
    thresholds: { advisory: number; warning: number; evacuate: number }
  ) => {
    const updated = await stationRepository.updateStationThresholds(stationId, thresholds);
    setStations((prev) => prev.map((s) => (s.id === stationId ? updated : s)));
  };

  const createUser = async (params: {
    name: string;
    email: string;
    role: any;
    barangay: string;
    phone: string;
  }) => {
    const newUser = await userRepository.createUser(params);
    setUsers((prev) => [...prev, newUser]);
  };

  const toggleUserStatus = async (id: string) => {
    const target = users.find((u) => u.id === id);
    if (!target) return;
    const newStatus = target.status === 'Active' ? 'Inactive' : 'Active';
    const updated = await userRepository.updateUserStatus(id, newStatus);
    setUsers((prev) => prev.map((u) => (u.id === id ? updated : u)));
  };

  const toggleOfflineMode = () => {
    setIsOffline((prev) => !prev);
  };

  const refreshData = async () => {
    await loadData();
  };

  return (
    <DashboardContext.Provider
      value={{
        stations,
        alerts,
        sosBeacons,
        users,
        selectedBarangay,
        isOffline,
        currentUser,
        metrics: {
          activeAlertsCount,
          criticalStationsCount,
          averageWaterLevelCm,
          activeSOSCount,
        },
        resolveAlert,
        acknowledgeAlert,
        createManualAlert,
        acknowledgeSOS,
        resolveSOS,
        updateStationThresholds,
        createUser,
        toggleUserStatus,
        setSelectedBarangay,
        toggleOfflineMode,
        refreshData,
      }}
    >
      {children}
    </DashboardContext.Provider>
  );
}

export function useDashboard() {
  const context = useContext(DashboardContext);
  if (!context) {
    throw new Error('useDashboard must be used within a DashboardProvider');
  }
  return context;
}
