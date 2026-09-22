"use client";
import { useEffect,useState } from "react";
import Link from "next/link";
import { accountRequest } from "@/lib/accounts";
import { FigmaIcon,InformationDialog } from "./DesignUI";
import { figmaAssets } from "@/lib/figma-assets";
export default function Login({onLogin}:{onLogin:()=>void}) {
  const [email,setEmail]=useState(""),[password,setPassword]=useState("");
  const [showPassword,setShowPassword]=useState(false),[loading,setLoading]=useState(false);
  const [error,setError]=useState(""),[setupAvailable,setSetupAvailable]=useState(false);
  const [info,setInfo]=useState<"google"|"privacy"|"terms"|null>(null);
  useEffect(()=>{let active=true;accountRequest<{available:boolean}>("setup").then(s=>{if(active)setSetupAvailable(s.available);}).catch(()=>{});return()=>{active=false;};},[]);
  async function submit(event:React.FormEvent) {
    event.preventDefault();if(loading)return;setLoading(true);setError("");
    try{await accountRequest("login","POST",{email:email.trim(),password});onLogin();}
    catch(e){setError(e instanceof Error?e.message:"Unable to sign in.");}finally{setLoading(false);}
  }
  return <div className="auth-screen"><section className="auth-card">
    <div className="auth-brand"><img src={figmaAssets.logo} alt="AGAPAY logo" width={39} height={39}/><h1>AGAPAY</h1></div>
    <p className="auth-caption">Sign in to Continue</p>
    <form onSubmit={submit} className="auth-form">
      <label htmlFor="login-email">Email<input id="login-email" type="email" autoComplete="username" required value={email} onChange={e=>setEmail(e.target.value)}/></label>
      <label htmlFor="login-password">Password<div className="password-field"><input id="login-password" type={showPassword?"text":"password"} autoComplete="current-password" required value={password} onChange={e=>setPassword(e.target.value)}/><button type="button" aria-label={showPassword?"Hide password":"Show password"} aria-pressed={showPassword} onClick={()=>setShowPassword(!showPassword)}><FigmaIcon name="eye"/></button></div></label>
      {error&&<p role="alert" className="form-error">{error}</p>}
      <button className="auth-submit" disabled={loading}>{loading?"Signing in…":"Continue"}</button>
    </form>
    <div className="auth-divider"><span/>OR<span/></div>
    <button className="google-button" onClick={()=>setInfo("google")}><FigmaIcon name="google" size={18}/>Continue with Google</button>
    <p className="auth-legal">By signing in, you agree to AGAPAY’s <button onClick={()=>setInfo("terms")}>Terms of Service</button> and <button onClick={()=>setInfo("privacy")}>Privacy Policy</button>.</p>
    {setupAvailable&&<Link className="auth-register" href="/register">Create administrator account</Link>}
  </section>{info&&<InformationDialog kind={info} onClose={()=>setInfo(null)}/>}</div>;
}
