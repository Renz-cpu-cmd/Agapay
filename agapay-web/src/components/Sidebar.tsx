"use client";
import Link from "next/link";
import { useAccount } from "@/context/AccountContext";
import { pagePaths, navigationGroup, type Page } from "@/lib/navigation";
import { FigmaIcon } from "./DesignUI";
import { figmaAssets } from "@/lib/figma-assets";
const navigation = [["dashboard","Dashboard"],["stations","Stations"],["alerts","Alerts"],["sos","SOS"],["analytics","Analytics"],["users","Users"],["health","System Health"],["mlConfiguration","ML Configuration"]] as const;
export default function Sidebar({ current, onLogout, sosCount }: { current: Page; onLogout: () => void; sosCount: number }) {
  const { user } = useAccount();
  const group = navigationGroup(current);
  return <aside className="design-sidebar">
    <Link className="brand" href="/dashboard" aria-label="AGAPAY dashboard"><img src={figmaAssets.logo} alt="" width={49} height={49}/><span>AGAPAY</span></Link>
    <nav aria-label="Main navigation">{navigation.filter(([id]) => id !== "users" || user.role === "admin").map(([id,label]) => {
      // Local demo counts must not masquerade as persistent sensor-alert totals.
      const count = id === "sos" ? sosCount : 0;
      return <Link key={id} className={`nav-link ${group === id ? "selected" : ""}`} aria-label={label} title={label} aria-current={current === id ? "page" : group === id ? "location" : undefined} href={pagePaths[id]}>
        <FigmaIcon inheritColor name={id === "mlConfiguration" ? "settings" : id} size={24}/><span>{label}</span>{count > 0 && <span className={`nav-count ${id}`}>{count}</span>}
      </Link>;
    })}</nav>
    <div className="sidebar-account"><FigmaIcon name="profile" size={28}/><div><span title={user.name}>{user.name}</span><small>{user.role === "officer" ? "LGU Officer" : user.role === "admin" ? "Administrator" : "Resident"}</small></div></div>
    <Link className={`sidebar-action ${current === "settings" ? "selected" : ""}`} href="/settings" aria-current={current === "settings" ? "page" : undefined}><FigmaIcon inheritColor name="settings" size={22}/>Settings</Link>
    <button className="sidebar-action" onClick={onLogout}><FigmaIcon inheritColor name="logout" size={22}/>LOG OUT</button>
  </aside>;
}
