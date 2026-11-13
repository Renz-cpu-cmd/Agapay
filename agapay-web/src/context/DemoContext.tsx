"use client";

import { createContext, useContext, useState, type Dispatch, type ReactNode, type SetStateAction } from "react";
import { alerts as initialAlerts, type Alert } from "@/data/mockData";

type DemoState = {
  alerts: Alert[];
  setAlerts: Dispatch<SetStateAction<Alert[]>>;
};

const DemoContext = createContext<DemoState | null>(null);

// UI-only state shared across routes. Replace with API repositories when the backend is connected.
export function DemoProvider({ children }: { children: ReactNode }) {
  const [alerts, setAlerts] = useState(initialAlerts);
  return <DemoContext.Provider value={{ alerts, setAlerts }}>{children}</DemoContext.Provider>;
}

export function useDemo() {
  const context = useContext(DemoContext);
  if (!context) throw new Error("useDemo requires DemoProvider");
  return context;
}
