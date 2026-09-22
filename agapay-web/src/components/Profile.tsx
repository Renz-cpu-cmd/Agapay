"use client";
import { useState } from "react";
import { useAccount } from "@/context/AccountContext";
import { accountRequest,type Account } from "@/lib/accounts";
import { FigmaIcon,Modal,LogoutDialog,InformationDialog } from "./DesignUI";
function EditProfile({onClose,onSaved}:{onClose:()=>void;onSaved:()=>void}) {
  const {user,setUser}=useAccount();const [busy,setBusy]=useState(false),[error,setError]=useState("");
  async function submit(event:React.FormEvent<HTMLFormElement>) {
    event.preventDefault();if(busy)return;const fields=new FormData(event.currentTarget);
    const password=String(fields.get("password")??""),current=String(fields.get("current_password")??"");
    setBusy(true);setError("");
    try{const saved=await accountRequest<Account>("me","PATCH",{name:fields.get("name"),email:fields.get("email"),phone:fields.get("phone"),barangay:fields.get("barangay"),...(password?{password}:{}),...(current?{current_password:current}:{})});setUser(saved);if(password){window.location.assign("/login");return;}onSaved();}
    catch(e){setError(e instanceof Error?e.message:"Unable to save your profile.");}finally{setBusy(false);}
  }
  return <Modal title="Edit profile" onClose={()=>{if(!busy)onClose();}}><h2>Edit profile</h2><form className="flex flex-col gap-4" onSubmit={submit}>
    {([["name","Full Name"],["email","Email"],["phone","Phone"],["barangay","Barangay"]] as const).map(([name,label])=><label key={name}>{label}<input className="design-input" name={name} required type={name==="email"?"email":name==="phone"?"tel":"text"} defaultValue={user[name]} maxLength={name==="email"?254:120}/></label>)}
    <p className="subtle-note">Your current password is required to change your email or password. A new password signs you out on all devices.</p>
    <label>Current Password<input className="design-input" name="current_password" type="password" autoComplete="current-password" maxLength={128}/></label>
    <label>New Password (optional)<input className="design-input" name="password" type="password" autoComplete="new-password" minLength={12} maxLength={128} placeholder="At least 12 characters"/></label>
    {error&&<p role="alert" className="form-error">{error}</p>}<div className="dialog-actions"><button className="design-button" type="button" onClick={onClose} disabled={busy}>CANCEL</button><button className="design-button primary" disabled={busy}>{busy?"SAVING…":"SAVE CHANGES"}</button></div>
  </form></Modal>;
}
export default function Profile() {
  const {user}=useAccount();const [edit,setEdit]=useState(false),[logout,setLogout]=useState(false),[saved,setSaved]=useState(false);
  const [info,setInfo]=useState<"about"|"privacy"|"language"|null>(null);
  return <div className="design-page settings-page"><p className="settings-caption">Account & Settings</p>
    {saved&&<p className="form-success" role="status">Your profile has been saved.</p>}
    <section className="design-panel account-card"><header><FigmaIcon name="account" size={48}/><div><h2>{user.name}</h2><small>{user.role==="officer"?"LGU Officer":user.role}</small></div><button aria-label="Edit profile" onClick={()=>setEdit(true)}><FigmaIcon name="edit"/></button></header>
      <div className="account-info"><div><FigmaIcon name="email" size={35}/><span>Email: {user.email}</span></div><div><FigmaIcon name="barangay" size={32}/><span>Barangay: {user.barangay}</span></div><div><FigmaIcon name="phone" size={33}/><span>Contact no. {user.phone}</span></div><div><FigmaIcon name="calendar" size={32}/><span>Member since: {new Date(user.created_at).toLocaleDateString("en-PH",{month:"long",year:"numeric",timeZone:"Asia/Manila"})}</span></div></div>
    </section>
    <section className="design-panel settings-group" aria-label="Preferences">
      <div className="settings-row"><FigmaIcon name="notifications" size={34}/><div className="row-label"><strong>Flood Alerts</strong><small>Push notifications are not connected yet</small></div><button className="settings-switch" role="switch" aria-label="Flood alert push notifications" aria-checked={false} disabled title="Push delivery is not configured"><span/></button></div>
      <div className="settings-row"><FigmaIcon name="location" size={32}/><div className="row-label"><strong>Location Services</strong><small>Resident SOS location is managed in the mobile app</small></div><button className="settings-switch" role="switch" aria-label="Resident location services" aria-checked={false} disabled title="Use the resident mobile app to grant location access"><span/></button></div>
      <button className="settings-row" onClick={()=>setInfo("language")}><FigmaIcon name="language" size={33}/><div className="row-label"><strong>Language</strong><small>Display Language for content</small></div><span className="row-value">English &gt;</span></button>
      <button className="settings-row" onClick={()=>setEdit(true)}><FigmaIcon name="home" size={31}/><div className="row-label"><strong>Barangay</strong><small>Your registered barangay for targeted alerts</small></div><span className="row-value">{user.barangay} &gt;</span></button>
    </section>
    <section className="design-panel settings-group"><button className="settings-row" onClick={()=>setInfo("about")}><FigmaIcon name="about"/><span className="row-label">About AGAPAY</span><span className="row-value">&gt;</span></button><button className="settings-row" onClick={()=>setInfo("privacy")}><FigmaIcon name="privacy" size={34}/><span className="row-label"><strong>Privacy Policy</strong><small>How AGAPAY handles your data</small></span><span className="row-value">&gt;</span></button></section>
    <button className="settings-logout" onClick={()=>setLogout(true)}>LOG OUT<FigmaIcon name="signout" size={26}/></button>
    {edit&&<EditProfile onClose={()=>setEdit(false)} onSaved={()=>{setEdit(false);setSaved(true);}}/>}{logout&&<LogoutDialog onClose={()=>setLogout(false)}/>}{info&&<InformationDialog kind={info} onClose={()=>setInfo(null)}/>}
  </div>;
}
