"use client";
import { useState } from "react";
import { useAccount } from "@/context/AccountContext";
import AccountSecurity from "./AccountSecurity";
import PrivacyCenter from "./PrivacyCenter";
import GeographicPreferences from "./GeographicPreferences";
import { ThemeSelector } from "@/context/ThemeContext";
import { accountRequest,AccountError,type Account } from "@/lib/accounts";
import { FigmaIcon,Modal,LogoutDialog,InformationDialog } from "./DesignUI";
function EditProfile({onClose,onSaved,onConflict}:{onClose:()=>void;onSaved:()=>void;onConflict:()=>void}) {
  const {user,setUser}=useAccount();const [busy,setBusy]=useState(false),[error,setError]=useState("");
  const [original]=useState(user);
  async function submit(event:React.FormEvent<HTMLFormElement>) {
    event.preventDefault();if(busy)return;const fields=new FormData(event.currentTarget);
    const password=String(fields.get("password")??""),current=String(fields.get("current_password")??"");
    setBusy(true);setError("");
    try{const saved=await accountRequest<Account>("me","PATCH",{expected_version:original.version,name:fields.get("name"),email:fields.get("email"),phone:fields.get("phone"),barangay:fields.get("barangay"),...(password?{password}:{}),...(current?{current_password:current}:{})});setUser(saved);if(password){window.location.assign("/login");return;}onSaved();}
    catch(e){if(e instanceof AccountError&&e.status===409){onConflict();return;}setError(e instanceof Error?e.message:"Unable to save your profile.");}finally{setBusy(false);}
  }
  return <Modal title="Edit profile" onClose={()=>{if(!busy)onClose();}}><h2>Edit profile</h2><form className="flex flex-col gap-4" onSubmit={submit}>
    {([["name","Full Name"],["email","Email"],["phone","Phone"],["barangay","Barangay"]] as const).map(([name,label])=><label key={name}>{label}<input className="design-input" name={name} required type={name==="email"?"email":name==="phone"?"tel":"text"} defaultValue={original[name]} maxLength={name==="email"?254:120}/></label>)}
    <p className="subtle-note">Your current password is required to change your email or password. A new password signs you out on all devices.</p>
    <label>Current Password<input className="design-input" name="current_password" type="password" autoComplete="current-password" maxLength={128}/></label>
    <label>New Password (optional)<input className="design-input" name="password" type="password" autoComplete="new-password" minLength={12} maxLength={128} placeholder="At least 12 characters"/></label>
    {error&&<p role="alert" className="form-error">{error}</p>}<div className="dialog-actions"><button className="design-button" type="button" onClick={onClose} disabled={busy}>CANCEL</button><button className="design-button primary" disabled={busy}>{busy?"SAVING…":"SAVE CHANGES"}</button></div>
  </form></Modal>;
}
export default function Profile() {
  const {user,setUser}=useAccount();const [conflicted,setConflicted]=useState(false),[refreshError,setRefreshError]=useState("");const [edit,setEdit]=useState(false),[logout,setLogout]=useState(false),[saved,setSaved]=useState(false);
  const [info,setInfo]=useState<"about"|"privacy"|"language"|null>(null);
  return <div className="design-page settings-page"><p className="settings-caption">Account & Settings</p>
    {conflicted&&<p role="alert">The account changed. The stale form and password fields were discarded. <button className="design-button" onClick={()=>void accountRequest<Account>("me").then(value=>{setUser(value);setConflicted(false);setRefreshError("");}).catch(e=>setRefreshError(e.message))}>Refresh profile and review</button>{refreshError}</p>}
    {saved&&<p className="form-success" role="status">Your profile has been saved.</p>}
    <section className="design-panel account-card"><header><FigmaIcon inheritColor name="account" size={48}/><div><h2>{user.name}</h2><small>{user.role==="officer"?"LGU Officer":user.role}</small></div><button aria-label="Edit profile" disabled={conflicted} onClick={()=>setEdit(true)}><FigmaIcon inheritColor name="edit"/></button></header>
      <div className="account-info"><div><FigmaIcon name="email" size={35}/><span>Email: {user.email}</span></div><div><FigmaIcon inheritColor name="barangay" size={32}/><span>Barangay: {user.barangay}</span></div><div><FigmaIcon inheritColor name="phone" size={33}/><span>Contact no. {user.phone}</span></div><div><FigmaIcon inheritColor name="calendar" size={32}/><span>Member since: {new Date(user.created_at).toLocaleDateString("en-PH",{month:"long",year:"numeric",timeZone:"Asia/Manila"})}</span></div></div>
    </section>
    <section className="design-panel settings-group" aria-label="Preferences">
      <div className="settings-row"><FigmaIcon inheritColor name="settings" size={32}/><div className="row-label"><strong>Appearance</strong><small>The map follows your theme. Saved in this browser.</small></div><ThemeSelector/></div>
      <div className="settings-row"><FigmaIcon inheritColor name="notifications" size={34}/><div className="row-label"><strong>Flood Alerts</strong><small>Resident push preferences are managed in the mobile app</small></div><button className="settings-switch" role="switch" aria-label="Flood alert push notifications" aria-checked={false} disabled title="Browser push is unavailable; use the resident mobile app"><span/></button></div>
      <div className="settings-row"><FigmaIcon inheritColor name="location" size={32}/><div className="row-label"><strong>Location Services</strong><small>Resident SOS location is managed in the mobile app</small></div><button className="settings-switch" role="switch" aria-label="Resident location services" aria-checked={false} disabled title="Use the resident mobile app to grant location access"><span/></button></div>
      <button className="settings-row" onClick={()=>setInfo("language")}><FigmaIcon inheritColor name="language" size={33}/><div className="row-label"><strong>Language</strong><small>English operational content; Filipino translation unavailable</small></div><span className="row-value">English &gt;</span></button>
      <button className="settings-row" disabled={conflicted} onClick={()=>setEdit(true)}><FigmaIcon inheritColor name="home" size={31}/><div className="row-label"><strong>Barangay</strong><small>Self-reported locality; delivery uses explicit subscriptions</small></div><span className="row-value">{user.barangay} &gt;</span></button>
    </section>
    <details className="design-panel p-4"><summary>Area preferences and response resources</summary><GeographicPreferences/><p><a href="/response-resources">Shelters and access registry</a></p></details>
    <details className="design-panel p-4"><summary>Privacy and data requests</summary><PrivacyCenter/></details>
    <details className="design-panel p-4"><summary>Account security and signed-in devices</summary><AccountSecurity/></details>
    <section className="design-panel settings-group"><button className="settings-row" onClick={()=>setInfo("about")}><FigmaIcon inheritColor name="about"/><span className="row-label">About AGAPAY</span><span className="row-value">&gt;</span></button><button className="settings-row" onClick={()=>setInfo("privacy")}><FigmaIcon inheritColor name="privacy" size={34}/><span className="row-label"><strong>Privacy Policy</strong><small>How AGAPAY handles your data</small></span><span className="row-value">&gt;</span></button></section>
    <button className="settings-logout" onClick={()=>setLogout(true)}>LOG OUT<FigmaIcon inheritColor name="signout" size={26}/></button>
    {edit&&<EditProfile onConflict={()=>{setEdit(false);setConflicted(true);setSaved(false);}} onClose={()=>setEdit(false)} onSaved={()=>{setEdit(false);setSaved(true);}}/>}{logout&&<LogoutDialog onClose={()=>setLogout(false)}/>}{info&&<InformationDialog kind={info} onClose={()=>setInfo(null)}/>}
  </div>;
}
