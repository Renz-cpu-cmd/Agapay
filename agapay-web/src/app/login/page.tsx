'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { ShieldCheck, Lock, Mail, AlertCircle, ArrowRight } from 'lucide-react';
import { APP_CONFIG } from '@/constants/theme';

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState('antonio.ramos@lgu.drrmc.gov.ph');
  const [password, setPassword] = useState('CommandOfficer2026!');
  const [rememberMe, setRememberMe] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setErrorMessage('');

    // Simulated auth delay
    setTimeout(() => {
      if (email && password) {
        router.push('/dashboard');
      } else {
        setErrorMessage('Invalid credentials. Please enter your officer email and password.');
        setIsLoading(false);
      }
    }, 600);
  };

  return (
    <div className="min-h-screen bg-slate-900 flex flex-col justify-center items-center p-4 relative overflow-hidden font-sans">
      {/* Background ambient lighting */}
      <div className="absolute -top-40 -left-40 w-96 h-96 bg-blue-600/20 rounded-full blur-3xl pointer-events-none"></div>
      <div className="absolute -bottom-40 -right-40 w-96 h-96 bg-blue-800/20 rounded-full blur-3xl pointer-events-none"></div>

      <div className="max-w-md w-full relative z-10">
        {/* Brand Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-brand-primary border border-blue-400/30 text-white font-black text-2xl shadow-xl shadow-blue-900/50 mb-4">
            ⚡
          </div>
          <h1 className="text-2xl font-black text-white tracking-wider">
            {APP_CONFIG.appName}
          </h1>
          <p className="text-xs font-bold text-blue-200 uppercase tracking-widest mt-1">
            Emergency Operations & Command Center
          </p>
          <p className="text-xs text-slate-400 mt-2">{APP_CONFIG.jurisdiction}</p>
        </div>

        {/* Login Card */}
        <div className="bg-white rounded-2xl p-8 shadow-2xl border border-slate-700/30">
          <div className="mb-6">
            <h2 className="text-lg font-black text-typography-primary">Officer Authentication</h2>
            <p className="text-xs text-typography-secondary mt-1">
              Sign in with your authorized LGU or DRRM credentials to access live flood telemetry.
            </p>
          </div>

          {errorMessage && (
            <div className="mb-4 p-3 rounded-xl bg-alert-evacuateBg text-alert-evacuateText border border-alert-evacuate/30 text-xs flex items-center gap-2">
              <AlertCircle size={16} />
              <span>{errorMessage}</span>
            </div>
          )}

          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-xs font-bold text-typography-secondary uppercase mb-1.5">
                Official Email / Officer ID
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-typography-muted">
                  <Mail size={16} />
                </div>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="officer@lgu.drrmc.gov.ph"
                  className="w-full text-xs font-semibold pl-10 pr-3.5 py-2.5 rounded-xl border border-border-light bg-surface-secondary focus:bg-white focus:ring-2 focus:ring-brand-primary outline-none transition-all"
                  required
                />
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="block text-xs font-bold text-typography-secondary uppercase">
                  Password
                </label>
                <a
                  href="#"
                  onClick={(e) => {
                    e.preventDefault();
                    alert('Password reset requested. Please contact the DRRM Systems Administrator.');
                  }}
                  className="text-xs font-bold text-brand-secondary hover:underline"
                >
                  Forgot Password?
                </a>
              </div>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-typography-muted">
                  <Lock size={16} />
                </div>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="w-full text-xs font-semibold pl-10 pr-3.5 py-2.5 rounded-xl border border-border-light bg-surface-secondary focus:bg-white focus:ring-2 focus:ring-brand-primary outline-none transition-all"
                  required
                />
              </div>
            </div>

            <div className="flex items-center justify-between pt-1">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(e) => setRememberMe(e.target.checked)}
                  className="w-4 h-4 rounded text-brand-primary focus:ring-brand-primary border-border-light"
                />
                <span className="text-xs font-medium text-typography-secondary">
                  Remember this workstation
                </span>
              </label>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-3 bg-brand-primary hover:bg-brand-primaryDark text-white text-xs font-black rounded-xl shadow-lg shadow-brand-primary/30 transition-all flex items-center justify-center gap-2 active:scale-98"
            >
              {isLoading ? (
                'Authorizing Command Access...'
              ) : (
                <>
                  <span>Sign In to Dashboard</span>
                  <ArrowRight size={16} />
                </>
              )}
            </button>
          </form>

          {/* Security Compliance Footer */}
          <div className="mt-6 pt-4 border-t border-border-light flex items-center justify-center gap-2 text-[11px] text-typography-muted">
            <ShieldCheck size={14} className="text-alert-normal" />
            <span>256-Bit Encrypted DRRM Dispatch Node</span>
          </div>
        </div>

        {/* Hotlines Footer */}
        <div className="mt-6 text-center text-xs text-slate-400 space-y-1">
          <p>
            Emergency DRRM Hotline: <strong className="text-white">911</strong> · Operations Desk:{' '}
            <strong className="text-white">(02) 8911-5061</strong>
          </p>
          <p className="text-[11px] text-slate-500">{APP_CONFIG.version}</p>
        </div>
      </div>
    </div>
  );
}
