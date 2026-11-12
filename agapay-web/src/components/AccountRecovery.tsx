"use client";
import {useEffect,useState} from "react";
import Link from "next/link";
import {accountRequest} from "@/lib/accounts";

export default function AccountRecovery(){
  const [available,setAvailable]=useState(false),[email,setEmail]=useState(""),[token,setToken]=useState(""),[password,setPassword]=useState("");
  const [purpose,setPurpose]=useState("password_reset"),[busy,setBusy]=useState(false),[message,setMessage]=useState(""),[error,setError]=useState("");
  useEffect(()=>{
    const fragment=new URLSearchParams(window.location.hash.slice(1));
    setToken(fragment.get("token")??"");setPurpose(fragment.get("action")??"password_reset");
    // The one-use code is never sent in a query string, browser referrer or server access log.
    window.history.replaceState(null,"",window.location.pathname);
    let active=true;void accountRequest<{recovery_available:boolean}>("capabilities").then(value=>{if(active)setAvailable(value.recovery_available);}).catch(()=>{});
    return()=>{active=false;};
  },[]);
  async function submit(path:string,body:unknown){
    if(busy)return;setBusy(true);setMessage("");setError("");
    try{const result=await accountRequest<{message:string}>(path,"POST",body);setMessage(result.message);if(path.endsWith("complete")){setPassword("");setToken("");}}
    catch(e){setError(e instanceof Error?e.message:"Unable to complete account recovery");}
    finally{setBusy(false);}
  }
  return <main className="auth-screen"><section className="auth-card flex flex-col gap-4"><h1>Account recovery and invitations</h1>
    <p>Verify your email or choose a new password using a time-limited code. Staff authenticator verification remains required after a password reset.</p>
    {available?<form className="auth-form" onSubmit={e=>{e.preventDefault();void submit("recovery/request",{email,purpose:purpose==="verify_email"?"verify_email":"password_reset"});}}>
      <label>Email<input type="email" autoComplete="email" required maxLength={254} value={email} onChange={e=>setEmail(e.target.value)}/></label>
      <label>Request<select className="design-input" value={purpose==="verify_email"?"verify_email":"password_reset"} onChange={e=>setPurpose(e.target.value)}><option value="password_reset">Reset password</option><option value="verify_email">Verify email</option></select></label>
      <button className="auth-submit" disabled={busy}>Send verification email</button>
    </form>:<p role="status">Email recovery is unavailable on this installation. Contact your AGAPAY operator. An existing code can still be submitted below.</p>}
    <form className="auth-form" onSubmit={e=>{e.preventDefault();void submit("recovery/complete",{token,...(password?{password}:{})});}}>
      <label>One-use email code<input autoComplete="off" required minLength={40} maxLength={128} value={token} onChange={e=>setToken(e.target.value.trim())}/></label>
      <label>New password (reset or invitation only)<input type="password" autoComplete="new-password" minLength={12} maxLength={128} value={password} onChange={e=>setPassword(e.target.value)}/></label>
      <button className="auth-submit" disabled={busy}>Confirm email code</button>
    </form>
    {message&&<p role="status">{message}</p>}{error&&<p role="alert">{error}</p>}<Link href="/login">Return to sign in</Link>
  </section></main>;
}
