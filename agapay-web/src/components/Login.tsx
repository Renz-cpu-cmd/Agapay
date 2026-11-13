"use client";
import { useEffect,useState } from "react";
import Link from "next/link";
import { accountRequest } from "@/lib/accounts";
import { FigmaIcon,InformationDialog } from "./DesignUI";
import { figmaAssets } from "@/lib/figma-assets";
import { ThemeSelector } from "@/context/ThemeContext";
export default function Login({onLogin}:{onLogin:()=>void}) {
  const [email,setEmail]=useState(""),[password,setPassword]=useState("");
  const [showPassword,setShowPassword]=useState(false),[loading,setLoading]=useState(false);
  const [error,setError]=useState(""),[setupAvailable,setSetupAvailable]=useState(false);
  const [info,setInfo]=useState<"privacy"|"terms"|null>(null);
  const [recoveryAvailable,setRecoveryAvailable]=useState(false);
  const [challenge,setChallenge]=useState<{challenge_token:string;secret?:string;mfa_enrollment_required:boolean}|null>(null);
  const [code,setCode]=useState("");const [recoveryCodes,setRecoveryCodes]=useState<string[]>([]);
  useEffect(()=>{let active=true;void accountRequest<{recovery_available:boolean}>("capabilities").then(c=>{if(active)setRecoveryAvailable(c.recovery_available);}).catch(()=>{});return()=>{active=false;};},[]);
  useEffect(()=>{let active=true;accountRequest<{available:boolean}>("setup").then(s=>{if(active)setSetupAvailable(s.available);}).catch(()=>{});return()=>{active=false;};},[]);
  async function submit(event:React.FormEvent) {
    event.preventDefault();if(loading)return;setLoading(true);setError("");
    try{
      if(challenge){const result=await accountRequest<{recovery_codes?:string[]}>("mfa/verify","POST",{challenge_token:challenge.challenge_token,code});setCode("");setChallenge(null);if(result.recovery_codes?.length)setRecoveryCodes(result.recovery_codes);else onLogin();}
      else{const result=await accountRequest<{user?:unknown;challenge_token?:string;secret?:string;mfa_enrollment_required?:boolean}>("login","POST",{email:email.trim(),password});setPassword("");if(result.challenge_token)setChallenge({challenge_token:result.challenge_token,secret:result.secret,mfa_enrollment_required:result.mfa_enrollment_required===true});else onLogin();}
    }
    catch(e){setError(e instanceof Error?e.message:"Unable to sign in.");}finally{setLoading(false);}
  }
  return <div className="auth-screen"><div className="auth-theme"><ThemeSelector/></div><section className="auth-card">
    <div className="auth-brand"><img src={figmaAssets.logo} alt="AGAPAY logo" width={39} height={39}/><h1>AGAPAY</h1></div>
    <p className="auth-caption">Sign in to Continue</p>
    {recoveryCodes.length>0?<div role="status"><h2>Save your single-use recovery codes</h2><p>Store these securely outside this device. They will not be shown again.</p><pre className="select-all">{recoveryCodes.join("\n")}</pre><button className="auth-submit" onClick={()=>{setRecoveryCodes([]);onLogin();}}>I saved my recovery codes</button></div>:<form onSubmit={submit} className="auth-form">
      {!challenge&&<><label htmlFor="login-email">Email<input id="login-email" type="email" autoComplete="username" required value={email} onChange={e=>setEmail(e.target.value)}/></label>
      <label htmlFor="login-password">Password<div className="password-field"><input id="login-password" type={showPassword?"text":"password"} autoComplete="current-password" required value={password} onChange={e=>setPassword(e.target.value)}/><button type="button" aria-label={showPassword?"Hide password":"Show password"} aria-pressed={showPassword} onClick={()=>setShowPassword(!showPassword)}><FigmaIcon name="eye"/></button></div></label>
      </>}
      {challenge&&<><h2>{challenge.mfa_enrollment_required?"Set up your staff authenticator":"Verify staff sign-in"}</h2>{challenge.secret&&<><p>Add AGAPAY manually in your authenticator using this key, then enter its six-digit code.</p><code className="break-all select-all">{challenge.secret}</code></>}<label>Authenticator or unused recovery code<input required autoComplete="one-time-code" maxLength={64} value={code} onChange={e=>setCode(e.target.value)}/></label><button type="button" onClick={()=>{setChallenge(null);setCode("");}}>Start sign-in again</button></>}
      {error&&<p role="alert" className="form-error">{error}</p>}
      <button className="auth-submit" disabled={loading}>{loading?"Signing in…":"Continue"}</button>
    </form>}
    {recoveryAvailable?<Link className="auth-register" href="/recover">Forgot password or verify email</Link>:<p className="subtle-note">Email recovery unavailable; contact your AGAPAY operator.</p>}
    <p className="auth-legal">By signing in, you agree to AGAPAY’s <button onClick={()=>setInfo("terms")}>Terms of Service</button> and <button onClick={()=>setInfo("privacy")}>Privacy Policy</button>.</p>
    {setupAvailable&&<Link className="auth-register" href="/register">Create administrator account</Link>}
  </section>{info&&<InformationDialog kind={info} onClose={()=>setInfo(null)}/>}</div>;
}
