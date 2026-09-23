"use client";
import Link from "next/link";
import { useAccount } from "@/context/AccountContext";
import { pagePaths, type Page } from "@/lib/navigation";
import { FigmaIcon } from "./DesignUI";
import { figmaAssets } from "@/lib/figma-assets";
const navigation = [["dashboard","Dashboard"],["stations","Stations"],["alerts","Alerts"],["sos","SOS Beacons"],["analytics","Analytics"],["users","Users"],["health","System Health"]] as const;
export default function Sidebar({ current, onLogout, sosCount }: { current: Page; onLogout: () => void; sosCount: number }) {
  const { user } = useAccount();
  return <aside className="design-sidebar">
    <Link className="brand" href="/dashboard" aria-label="AGAPAY dashboard"><img src={figmaAssets.logo} alt="" width={49} height={49}/><span>AGAPAY</span></Link>
    <nav aria-label="Main navigation">{navigation.filter(([id]) => id !== "users" || user.role === "admin").map(([id,label]) => {
      // Local demo counts must not masquerade as persistent sensor-alert totals.
      const count = id === "sos" ? sosCount : 0;
      return <Link key={id} className={`nav-link ${current === id ? "selected" : ""}`} aria-current={current === id ? "page" : undefined} href={pagePaths[id]}>
        <FigmaIcon name={id} size={id === "stations" ? 28 : 24}/><span>{label}</span>{count > 0 && <span className={`nav-count ${id}`}>{count}</span>}
      </Link>;
    })}</nav>
    <div className="sidebar-account"><FigmaIcon name="profile" size={28}/><div><span title={user.name}>{user.name}</span><small>{user.role === "officer" ? "LGU Officer" : user.role === "admin" ? "Administrator" : "Resident"}</small></div></div>
    <Link className={`sidebar-action ${current === "settings" ? "selected" : ""}`} href="/settings" aria-current={current === "settings" ? "page" : undefined}><FigmaIcon name="settings" size={22}/>Settings</Link>
    <button className="sidebar-action" onClick={onLogout}><FigmaIcon name="logout" size={22}/>LOG OUT</button>
  </aside>;
}
