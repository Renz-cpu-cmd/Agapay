"use client";
import {useEffect,useState} from "react";
import {accountRequest} from "@/lib/accounts";
import {useAccount} from "@/context/AccountContext";
type Security={email_verified:boolean;mfa_enabled:boolean;sessions:{id:string;audience:string;current:boolean;expires_at:string;mfa_verified:boolean}[];devices:{id:string;platform:string;enabled:boolean}[]};
type Challenge={challenge_token:string;secret?:string;mfa_enrollment_required:boolean};
type Audit={id:number;actor_label:string;action:string;reason:string;subject_type:string;subject_id:string;created_at:string;before:unknown;after:unknown};
export default function AccountSecurity(){
  const {user}=useAccount();
  const [data,setData]=useState<Security|null>(null),[available,setAvailable]=useState(false),[mfaAvailable,setMfaAvailable]=useState(false);
  const [error,setError]=useState(""),[message,setMessage]=useState(""),[busy,setBusy]=useState(false),[password,setPassword]=useState(""),[code,setCode]=useState("");
  const [challenge,setChallenge]=useState<Challenge|null>(null),[recoveryCodes,setRecoveryCodes]=useState<string[]>([]),[audits,setAudits]=useState<Audit[]>([]);
  async function load(){try{setData(await accountRequest<Security>("security"));const caps=await accountRequest<{recovery_available:boolean;mfa_available:boolean}>("capabilities");setAvailable(caps.recovery_available);setMfaAvailable(caps.mfa_available);}catch(e){setError(e instanceof Error?e.message:"Security information unavailable");}}
  useEffect(()=>{void load();},[]);
  async function revoke(path:string,body:Record<string,unknown>,signOut=false){
    if(busy)return;setBusy(true);setError("");
    try{await accountRequest(path,"POST",{...body,reason:"Account owner explicitly revoked this authorization"});if(signOut){window.location.assign("/login");return;}await load();}
    catch(e){setError(e instanceof Error?e.message:"Unable to revoke authorization");}finally{setBusy(false);}
  }
  async function mfa(){
    if(busy)return;setBusy(true);setError("");
    try{
      if(challenge){const result=await accountRequest<{recovery_codes:string[]}>("mfa/verify","POST",{challenge_token:challenge.challenge_token,code});setRecoveryCodes(result.recovery_codes??[]);setChallenge(null);setCode("");await load();}
      else{setChallenge(await accountRequest<Challenge>("mfa/start","POST",{current_password:password,...(code?{code}:{})}));setPassword("");setCode("");}
    }catch(e){setError(e instanceof Error?e.message:"Authenticator operation failed");}finally{setBusy(false);}
  }
  return <section className="design-panel p-4 flex flex-col gap-4"><h2>Account security</h2>
    {!data?<p>Security information unavailable until loaded.</p>:<>
      <p>Email {data.email_verified?"verified":"not verified"} · Authenticator {data.mfa_enabled?"enabled":"not enrolled"}</p>
      {available&&!data.email_verified&&<button className="design-button" disabled={busy} onClick={()=>{setBusy(true);void accountRequest<{message:string}>("recovery/request","POST",{email:user.email,purpose:"verify_email"}).then(r=>setMessage(r.message)).catch(e=>setError(e.message)).finally(()=>setBusy(false));}}>Send email verification</button>}
      <a href="/recover">Enter an email verification or recovery code</a>
      <h3>Signed-in sessions</h3><p className="subtle-note">Expiry alone does not disable push. Explicit revocation removes the selected session and its push authorization.</p>
      {data.sessions.map(session=><div className="flex flex-wrap justify-between gap-2" key={session.id}><span>{session.audience} · {session.current?"This session":"Other session"} · expires {new Date(session.expires_at).toLocaleString()}</span><button className="design-button danger" disabled={busy} onClick={()=>void revoke("security/revoke-session",{session_id:session.id},session.current)}>Revoke session</button></div>)}
      <button className="design-button danger" disabled={busy} onClick={()=>void revoke("security/revoke-all",{},true)}>Sign out every session and disable account push devices</button>
      <h3>Push devices</h3>{data.devices.length?data.devices.map(device=><div className="flex justify-between gap-2" key={device.id}><span>{device.platform} · {device.enabled?"enabled":"disabled"}</span><button className="design-button" disabled={busy||!device.enabled} onClick={()=>void revoke("security/revoke-device",{device_id:device.id})}>Revoke device and its session</button></div>):<p>No push devices registered for this account.</p>}
      {mfaAvailable&&data.email_verified?<form className="flex flex-col gap-3" onSubmit={e=>{e.preventDefault();void mfa();}}><h3>{data.mfa_enabled?"Rotate authenticator":"Enroll authenticator"}</h3>
        {challenge?<><p>Add this account manually in your authenticator app, then enter its six-digit code.</p><code className="break-all select-all">{challenge.secret}</code></>:<label>Current password<input className="design-input w-full" type="password" autoComplete="current-password" required value={password} onChange={e=>setPassword(e.target.value)}/></label>}
        {(challenge||data.mfa_enabled)&&<label>{challenge?"New authenticator code":"Current authenticator or unused recovery code"}<input className="design-input w-full" autoComplete="one-time-code" required maxLength={64} value={code} onChange={e=>setCode(e.target.value)}/></label>}
        {challenge&&<button type="button" className="design-button" disabled={busy} onClick={()=>{setChallenge(null);setCode("");}}>Restart setup with current credentials</button>}
        <button className="design-button" disabled={busy}>{challenge?"Confirm authenticator":"Start authenticator setup"}</button>
      </form>:<p className="subtle-note">Authenticator setup requires a verified email and configured identity encryption.</p>}
    </>}
    {recoveryCodes.length>0&&<div role="status"><h3>Save these recovery codes now</h3><p>Each code works once. Store them securely outside this device. They will not be shown again.</p><pre className="select-all">{recoveryCodes.join("\n")}</pre><button className="design-button" onClick={()=>setRecoveryCodes([])}>I saved my codes</button></div>}
    {message&&<p role="status">{message}</p>}{error&&<p role="alert">{error}</p>}<button className="design-button" disabled={busy} onClick={()=>void load()}>Refresh account security</button>
    {user.role==="admin"&&<><button className="design-button" onClick={()=>void accountRequest<Audit[]>("audit").then(setAudits).catch(e=>setError(e.message))}>Load recent mutation audit</button>{audits.map(a=><details key={a.id}><summary>{a.action} · {a.actor_label} · {a.subject_type} {a.subject_id} · {a.created_at}</summary><p>{a.reason}</p><pre className="whitespace-pre-wrap break-all">{JSON.stringify({before:a.before,after:a.after},null,2)}</pre></details>)}</>}
  </section>;
}
