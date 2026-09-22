"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { usePathname } from "next/navigation";
import Sidebar from "./Sidebar";
import Header from "./Header";
import { LogoutDialog } from "./DesignUI";
import { pageFromPath } from "@/lib/navigation";
import { DemoProvider, useDemo } from "@/context/DemoContext";
import { AccountProvider } from "@/context/AccountContext";
import { SosProvider, useSos } from "@/context/SosContext";
import { MonitoringProvider, useMonitoring } from "@/context/MonitoringContext";
import { type Account } from "@/lib/accounts";

function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const current = pageFromPath(pathname);
  const contentRef = useRef<HTMLElement>(null);
  const [showLogout, setShowLogout] = useState(false);
  const { alerts } = useDemo();
  const { page, error: sosError } = useSos();
  const { error: monitoringError } = useMonitoring();

  useEffect(() => {
    contentRef.current?.scrollTo({ top: 0, left: 0 });
  }, [pathname]);

  return (
    <div className="command-center flex h-dvh overflow-hidden" style={{ background: "#000000" }}>
      <Sidebar current={current} onLogout={() => setShowLogout(true)}
        sosCount={page?.counts.ACTIVE ?? 0}
        alertCount={alerts.filter((a) => a.status === "ACTIVE").length} />
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        <Header current={current} />
        {monitoringError && <p role="alert" className="px-4 py-2 text-xs text-amber-400">Live monitoring unavailable. The last received values may be out of date.</p>}
        {sosError && <p role="alert" className="px-4 py-2 text-xs text-amber-400">SOS connection unavailable. Displayed requests and counts may be out of date.</p>}
        <main ref={contentRef} id="main-content" className="command-content" tabIndex={0} aria-label="Page content">{children}</main>
        {showLogout && <LogoutDialog onClose={() => setShowLogout(false)}/> }
      </div>
    </div>
  );
}

export default function CommandCenter({ children, user }: { children: ReactNode; user: Account }) {
  return <AccountProvider initialUser={user}><MonitoringProvider><DemoProvider><SosProvider><Shell>{children}</Shell></SosProvider></DemoProvider></MonitoringProvider></AccountProvider>;
}
