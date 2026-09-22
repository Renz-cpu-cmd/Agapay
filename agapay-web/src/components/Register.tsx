"use client";
import { figmaAssets } from "@/lib/figma-assets";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { accountRequest } from "@/lib/accounts";

type SetupStatus = { available: boolean; reason: string };
const fieldClass = "w-full rounded border border-[#002967] bg-[#001434] px-3 py-2.5 text-sm text-slate-200 outline-none transition-colors focus:border-sky-500 disabled:opacity-60";
const labelClass = "font-ui text-xs font-semibold uppercase tracking-widest text-slate-400";

export default function Register() {
  const [status, setStatus] = useState<SetupStatus | null>(null);
  const [checking, setChecking] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [barangay, setBarangay] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  const checkSetup = useCallback(async () => {
    setChecking(true); setError("");
    try { setStatus(await accountRequest<SetupStatus>("setup")); }
    catch (e) { setError(e instanceof Error ? e.message : "Unable to check registration. Please try again."); }
    finally { setChecking(false); }
  }, []);
  useEffect(() => { void checkSetup(); }, [checkSetup]);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError("");
    if (password !== confirmation) { setError("Passwords do not match. Please enter the same password twice."); return; }
    if (!name.trim() || !barangay.trim()) { setError("Enter your name and barangay."); return; }
    setLoading(true);
    try {
      await accountRequest("setup", "POST", { name: name.trim(), email: email.trim(), phone: phone.trim(), barangay: barangay.trim(), password });
      setPassword(""); setConfirmation("");
      window.location.assign("/dashboard");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to create your account. Please try again.");
      // Another tab may have completed setup, or the account may have been saved
      // before the connection was interrupted. Keep sign-in available either way.
      try { setStatus(await accountRequest<SetupStatus>("setup")); } catch { /* Preserve the submission error. */ }
    } finally { setLoading(false); }
  }

  return <main className="auth-screen">
    <section className="registration-card">
      <header className="text-center flex flex-col items-center gap-2">
        <div className="flex items-center gap-2 mb-1">
          <img src={figmaAssets.logo} alt="" width={39} height={39}/>
          <span className="font-ui text-2xl font-bold tracking-[0.25em] text-sky-500">AGAPAY</span>
        </div>
        <h1 className="font-ui text-2xl font-semibold text-slate-100 mt-2">Create administrator account</h1>
        <p className="text-xs leading-relaxed text-slate-400 max-w-sm">Set up your first account to manage users and review practice SOS requests.</p>
      </header>

      {checking && <p role="status" className="text-sm text-center text-slate-400">Checking account setup…</p>}
      {error && <p role="alert" className="rounded border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs leading-relaxed text-red-400">{error}</p>}
      {!checking && !status && <button type="button" onClick={() => void checkSetup()} className="text-sm text-sky-400">Try again</button>}
      {!checking && status && !status.available && <p role="status" className="rounded border border-sky-500/20 bg-sky-500/5 p-4 text-sm leading-relaxed text-slate-300">{status.reason}</p>}
      {!checking && status?.available && <form onSubmit={submit} className="flex flex-col gap-4">
        <fieldset disabled={loading} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5"><label className={labelClass} htmlFor="register-name">Full name</label><input id="register-name" name="name" autoComplete="name" required maxLength={120} value={name} onChange={(e) => setName(e.target.value)} className={fieldClass} placeholder="Your name" /></div>
          <div className="flex flex-col gap-1.5"><label className={labelClass} htmlFor="register-email">Email</label><input id="register-email" name="email" type="email" autoComplete="username" required maxLength={254} value={email} onChange={(e) => setEmail(e.target.value)} className={fieldClass} placeholder="admin@example.com" /></div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="flex flex-col gap-1.5"><label className={labelClass} htmlFor="register-phone">Phone</label><input id="register-phone" name="phone" type="tel" autoComplete="tel" required minLength={7} maxLength={30} value={phone} onChange={(e) => setPhone(e.target.value)} className={fieldClass} placeholder="09XXXXXXXXX" /></div>
            <div className="flex flex-col gap-1.5"><label className={labelClass} htmlFor="register-barangay">Barangay</label><input id="register-barangay" name="barangay" autoComplete="address-level3" required maxLength={120} value={barangay} onChange={(e) => setBarangay(e.target.value)} className={fieldClass} placeholder="San Vicente" /></div>
          </div>
          <div className="flex flex-col gap-1.5"><label className={labelClass} htmlFor="register-password">Password</label><input id="register-password" name="password" type={showPassword ? "text" : "password"} autoComplete="new-password" required minLength={12} maxLength={128} aria-describedby="password-help" value={password} onChange={(e) => setPassword(e.target.value)} className={fieldClass} /><p id="password-help" className="text-xs text-slate-500">Use 12–128 characters.</p></div>
          <div className="flex flex-col gap-1.5"><label className={labelClass} htmlFor="register-confirmation">Confirm password</label><input id="register-confirmation" name="confirmation" type={showPassword ? "text" : "password"} autoComplete="new-password" required minLength={12} maxLength={128} value={confirmation} onChange={(e) => setConfirmation(e.target.value)} className={fieldClass} /></div>
          <button type="button" aria-pressed={showPassword} onClick={() => setShowPassword(!showPassword)} className="self-end text-xs text-sky-400">{showPassword ? "Hide passwords" : "Show passwords"}</button>
          <button type="submit" className="w-full rounded bg-sky-500 py-3 font-ui font-bold text-sm uppercase tracking-widest text-white transition-colors hover:bg-sky-400 disabled:opacity-50">{loading ? "Creating account…" : "Create account"}</button>
        </fieldset>
      </form>}
      <p className="text-center text-xs text-slate-400">Already have an account? <Link href="/login" className="text-sky-400 underline underline-offset-4">Sign in</Link></p>
      <p className="text-center font-data text-xs text-slate-600">AGAPAY v2.0.0 · LGU Command Center</p>
    </section>
  </main>;
}
