"use client";

import { useState, type ReactNode } from "react";
import { useDialog } from "@/hooks/useDialog";
import { figmaAssets } from "@/lib/figma-assets";
import {PrivacyNotice} from "./PrivacyCenter";
import { accountRequest } from "@/lib/accounts";

export function FigmaIcon({ name, size = 24, className = "", inheritColor = false }: { name: keyof typeof figmaAssets; size?: number; className?: string; inheritColor?: boolean }) {
  // Keep the exported silhouette, but let monochrome controls share their
  // label's selected/muted color. Image paint cannot inherit currentColor.
  const mask = figmaAssets[name].replace("/website/", "/website/monochrome/");
  if (inheritColor) return <span aria-hidden="true" className={`figma-icon figma-icon-inherit ${className}`} style={{ width: size, height: size, maskImage: `url("${mask}")`, WebkitMaskImage: `url("${mask}")` }} />;
  return <img src={figmaAssets[name]} alt="" width={size} height={size} className={`figma-icon ${className}`} style={{ width: size, height: size }} />;
}

export function Modal({ title, children, onClose, className = "" }: { title: string; children: ReactNode; onClose: () => void; className?: string }) {
  const ref = useDialog(onClose);
  return <div ref={ref} role="dialog" aria-modal="true" aria-label={title} tabIndex={-1} className="design-overlay">
    <div className={`design-modal ${className}`}>{children}</div>
  </div>;
}

export function LogoutDialog({ onClose }: { onClose: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function logout() {
    if (busy) return;
    setBusy(true); setError("");
    try { await accountRequest("logout", "POST"); window.location.assign("/login"); }
    catch (e) { setError(e instanceof Error ? e.message : "Unable to sign out."); setBusy(false); }
  }
  return <Modal title="Confirm logout" onClose={() => { if (!busy) onClose(); }} className="logout-dialog">
    <h2>Are you sure you want to LOG OUT?</h2>
    {error && <p role="alert" className="form-error">{error}</p>}
    <button className="design-button outline" disabled={busy} onClick={logout}>{busy ? "SIGNING OUT…" : "LOG OUT"}</button>
    <button className="design-button" disabled={busy} onClick={onClose}>CANCEL</button>
  </Modal>;
}

export function InformationDialog({ kind, onClose }: { kind: "about" | "privacy" | "terms" | "google" | "language"; onClose: () => void }) {
  const content = {
    about: ["About AGAPAY", "AGAPAY is a community flood early-warning capstone for Urdaneta City University. It brings station monitoring, flood alert tiers, and resident SOS requests together for local officers.", "Station source, quality and timestamps identify each feed. SOS requests are stored by the connected account service; acknowledging them does not dispatch emergency responders."],
    privacy: ["Privacy information", "AGAPAY stores account details and SOS requests, including the location and contact details submitted by residents. Authorized staff can review these requests and record their acknowledgement and resolution.", "Opening an SOS map shares the submitted coordinates with Google Maps. Your password is hashed by the account service."],
    terms: ["Terms of use", "AGAPAY station readings and predictions are not official flood advice. Follow official local authority advisories.", "SOS actions record a request in AGAPAY for responders."],
    google: ["Google sign-in", "Google sign-in is included in the design, but a Google identity provider has not been configured for this project.", "Use your AGAPAY email and password to sign in."],
    language: ["Display language", "English is the available website language.", "Filipino translation is not available yet. Your account and alerts continue to use English."],
  }[kind];
  return <Modal title={content[0]} onClose={onClose}><h2>{content[0]}</h2>{kind==="privacy"?<PrivacyNotice/>:content.slice(1).map(p => <p className="dialog-copy" key={p}>{p}</p>)}<button className="design-button primary" onClick={onClose}>CLOSE</button></Modal>;
}
