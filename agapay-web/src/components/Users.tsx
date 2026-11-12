"use client";

import { useEffect, useState } from "react";
import { FigmaIcon } from "./DesignUI";
import { useDialog } from "@/hooks/useDialog";
import { accountRequest, AccountError, type Account } from "@/lib/accounts";
import { useAccount } from "@/context/AccountContext";

type User = Account & { status: string; joinedAt: string };
type SaveUser = Pick<Account, "name" | "email" | "phone" | "barangay" | "role"> & { password?: string; reason:string };
function displayUser(user: Account): User {
  return { ...user, status: user.is_active ? "Active" : "Inactive", joinedAt: new Date(user.created_at).toLocaleDateString("en-PH", { year: "numeric", month: "short", day: "numeric", timeZone: "Asia/Manila" }) };
}

const roleColor: Record<User["role"], string> = {
  admin: "var(--adaptive-blue, #0ea5e9)",
  officer: "var(--adaptive-warning, #f5df00)",
  resident: "var(--adaptive-success, #00e83a)",
};

function AddUserModal({ onClose, onSave, user, invitation }: { invitation:boolean; onClose: () => void; onSave: (user: SaveUser) => Promise<void>; user?: User }) {
  const dialogRef = useDialog(onClose);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const name = String(data.get('Full Name') ?? '').trim();
    const email = String(data.get('Email') ?? '').trim();
    if (!name || !email) { setError('Please enter a name and email.'); return; }
    setBusy(true); setError("");
    try {
      const password = String(data.get("Password") ?? "");
      await onSave({ name, email, role: data.get("role") as User["role"], phone: String(data.get("Phone") ?? "").trim(), barangay: String(data.get("barangay") ?? "").trim(), reason:String(data.get("reason")??"").trim(), ...(password ? { password } : {}) });
    } catch (error) { setError(error instanceof Error ? error.message : "Unable to save account."); setBusy(false); }
  }
  return (
    <div ref={dialogRef} role="dialog" aria-modal="true" aria-label="User details" tabIndex={-1} className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: "rgba(0,0,0,0.8)" }}>
      <form onSubmit={submit} className="w-96 p-6 flex flex-col gap-4" style={{ background: "var(--adaptive-surface, #00112e)", border: "1px solid #002967", borderRadius: "4px" }}>
        <div className="flex items-center justify-between">
          <h3 className="font-ui font-700 text-sm" style={{ color: "var(--adaptive-text, #ffffff)" }}>{user ? "Edit User" : "Add User"}</h3>
          <button aria-label="Close dialog" type="button" onClick={onClose} style={{ color: "var(--adaptive-muted, #8190a4)" }}>✕</button>
        </div>
        {error && <p role="alert" className="text-xs text-red-400">{error}</p>}
        {[
          { label: "Full Name", placeholder: "Juan Santos" },
          { label: "Email", placeholder: "j.santos@urdaneta.gov.ph" },
          { label: "Phone", placeholder: "+63 912 345 6789" },
          { label: "Password", placeholder: user ? "Leave blank to keep password" : "At least 12 characters" },
        ].filter(field=>!(invitation&&!user&&field.label==="Password")).map(({ label, placeholder }) => (
          <div key={label} className="flex flex-col gap-1.5">
            <label htmlFor={`user-${label}`} className="font-ui text-xs tracking-wide" style={{ color: "var(--adaptive-muted, #8190a4)" }}>{label}</label>
            <input
              id={`user-${label}`}
              name={label}
              defaultValue={label === "Full Name" ? user?.name : label === "Email" ? user?.email : label === "Phone" ? user?.phone : ""}
              minLength={label === "Password" ? 12 : undefined}
              maxLength={label === "Password" ? 128 : undefined}
              required={label !== "Password" || !user}
              autoComplete={label === "Password" ? "new-password" : "off"}
              placeholder={placeholder}
              type={label === "Password" ? "password" : label === "Email" ? "email" : "text"}
              className="px-3 py-2 text-sm outline-none"
              style={{ background: "var(--adaptive-surface, #001434)", border: "1px solid #002967", borderRadius: "4px", color: "var(--adaptive-text, #ffffff)" }}
            />
          </div>
        ))}
        <div className="flex flex-col gap-1.5">
          <label className="font-ui text-xs tracking-wide" style={{ color: "var(--adaptive-muted, #8190a4)" }}>Role</label>
          <select aria-label="Role" name="role" defaultValue={user?.role ?? "officer"} className="px-3 py-2 text-sm outline-none" style={{ background: "var(--adaptive-surface, #001434)", border: "1px solid #002967", borderRadius: "4px", color: "var(--adaptive-text, #ffffff)" }}>
            <option>officer</option>
            <option>resident</option>
            <option>admin</option>
          </select>
        </div>
        <div className="flex flex-col gap-1.5">
          <label className="font-ui text-xs tracking-wide" style={{ color: "var(--adaptive-muted, #8190a4)" }}>Barangay</label>
          <input required aria-label="Barangay" name="barangay" defaultValue={user?.barangay ?? ""} placeholder="San Vicente" className="px-3 py-2 text-sm outline-none" style={{ background: "var(--adaptive-surface, #001434)", border: "1px solid #002967", borderRadius: "4px", color: "var(--adaptive-text, #ffffff)" }}/>
        </div>
        <label>Reason for account change<input className="design-input w-full" name="reason" required minLength={3} maxLength={500}/></label>
        {invitation&&!user&&<p className="subtle-note">An invitation will be emailed. The recipient verifies ownership and chooses their own password. Staff MFA remains required.</p>}
        <div className="flex gap-3 mt-2">
          <button type="button" onClick={onClose} className="flex-1 py-2 font-ui text-xs font-700" style={{ background: "var(--adaptive-surface, #001637)", color: "var(--adaptive-secondary, #64748b)", borderRadius: "4px" }}>CANCEL</button>
          <button disabled={busy} type="submit" className="flex-1 py-2 font-ui text-xs font-700 hover:brightness-90 disabled:opacity-50" style={{ background: "var(--adaptive-blue, #0ea5e9)", color: "var(--adaptive-action-foreground, #000)", borderRadius: "4px" }}>{busy ? "SAVING..." : user ? "SAVE CHANGES" : "CREATE USER"}</button>
        </div>
      </form>
    </div>
  );
}

export default function Users() {
  const [users, setUsers] = useState<User[]>([]);
  const { user: viewer, setUser } = useAccount();
  const [blocked,setBlocked]=useState(false),[invitation,setInvitation]=useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [updating, setUpdating] = useState<number | null>(null);
  useEffect(() => {
    let active = true;
    void accountRequest<{invitations_available:boolean}>("capabilities").then(c=>{if(active)setInvitation(c.invitations_available);}).catch(()=>{});
    accountRequest<Account[]>("users").then(data => { if (active) setUsers(data.map(displayUser)); })
      .catch(error => { if (active) setError(error.message); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);
  async function toggleUser(user: User) {
    if(blocked)return;const reason=window.prompt("Reason for changing account activation (required)");if(!reason||reason.trim().length<3)return;
    setUpdating(user.id); setError("");
    try {
      const saved = await accountRequest<Account>(`users/${user.id}`, "PATCH", { is_active: !user.is_active, expected_version:user.version, reason });
      setUsers(items => items.map(item => item.id === saved.id ? displayUser(saved) : item));
    } catch (error) { if(error instanceof AccountError&&error.status===409)setBlocked(true);setError(error instanceof Error ? error.message : "Unable to update account."); }
    finally { setUpdating(null); }
  }
  const [editing, setEditing] = useState<User | undefined>();
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState("All");
  const [showAdd, setShowAdd] = useState(false);

  const filtered = users.filter((u) => {
    if (roleFilter !== "All" && u.role !== roleFilter) return false;
    if (search && !u.name.toLowerCase().includes(search.toLowerCase()) && !u.email.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  return (
    <div className="design-page users-screen">
      <button className="design-button" onClick={()=>{setLoading(true);void accountRequest<Account[]>("users").then(values=>{setUsers(values.map(displayUser));setBlocked(false);setError("");}).catch(e=>setError(e.message)).finally(()=>setLoading(false));}}>Refresh accounts and review newer records</button>
      {error && <p role="alert" className="text-xs text-red-400">{error} <button onClick={() => window.location.reload()} className="underline">Retry</button></p>}
      {loading && <p role="status" className="text-xs text-slate-400">Loading accounts...</p>}
      {/* Top row */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 flex-wrap gap-3">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            aria-label="Search users" placeholder="Search users..."
            className="px-3 py-1.5 text-xs outline-none w-52 max-w-full"
            style={{ background: "var(--adaptive-surface, #00112e)", border: "1px solid #002967", borderRadius: "4px", color: "var(--adaptive-text, #ffffff)" }}
          />
          <select
            aria-label="User role filter" value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value)}
            className="px-3 py-1.5 text-xs outline-none"
            style={{ background: "var(--adaptive-surface, #00112e)", border: "1px solid #002967", borderRadius: "4px", color: "var(--adaptive-secondary, #64748b)" }}
          >
            {["All","admin","officer","resident"].map(o => <option key={o}>{o}</option>)}
          </select>
        </div>
        <button
          disabled={blocked||loading} onClick={() => { setEditing(undefined); setShowAdd(true); }}
          className="flex items-center gap-2 font-ui text-xs font-700 px-4 py-1.5 transition-[filter] hover:brightness-90"
          style={{ background: "var(--adaptive-blue, #0ea5e9)", color: "var(--adaptive-action-foreground, #000)", borderRadius: "4px" }}
        >
          + Add User
        </button>
      </div>

      {/* Summary by role */}
      <div className="card-grid users-role-summary">
        {(["admin","officer","resident"] as const).map((role) => (
          <div key={role} className="p-3 flex items-center gap-3" style={{ background: "var(--adaptive-surface, #00112e)", border: "1px solid #002967", borderRadius: "4px" }}>
            <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 font-ui font-bold text-xs"
              style={{ background: `color-mix(in srgb, ${roleColor[role]} 9%, transparent)`, color: roleColor[role] }}>
              {users.filter(u=>u.role===role).length}
            </div>
            <div>
              <p className="font-ui font-700 text-xs capitalize" style={{ color: roleColor[role] }}>{role}s</p>
              <p className="text-xs" style={{ color: "var(--adaptive-secondary, #64748b)" }}>{users.filter(u=>u.role===role && u.status==="Active").length} active</p>
            </div>
          </div>
        ))}
      </div>

      {/* Table */}
      <div role="region" aria-label="User accounts table" tabIndex={0} style={{ background: "var(--adaptive-surface, #00112e)", border: "1px solid #002967", borderRadius: "4px", overflowX: "auto" }}>
        <table className="w-full">
          <thead>
            <tr style={{ borderBottom: "1px solid #002967" }}>
              {["Name","Email","Role","Barangay","Joined","Status","Action"].map(h => (
                <th key={h} className="text-left px-4 py-2.5 font-ui font-700 text-xs tracking-wide" style={{ color: "var(--adaptive-muted, #8190a4)", letterSpacing: "0.1em" }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map((u) => (
              <tr key={u.id} style={{ borderBottom: "1px solid #000916" }}>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2.5">
                    <FigmaIcon name="account" size={24}/>
                    <span className="font-ui text-xs font-600" style={{ color: "var(--adaptive-text, #ffffff)" }}>{u.name}</span>
                  </div>
                </td>
                <td className="px-4 py-3 font-data text-xs" style={{ color: "var(--adaptive-muted, #8190a4)" }}>{u.email}</td>
                <td className="px-4 py-3">
                  <span className="font-ui font-700 text-xs px-2 py-0.5 rounded-sm capitalize"
                    style={{ background: `color-mix(in srgb, ${roleColor[u.role]} 9%, transparent)`, color: roleColor[u.role], border: `1px solid color-mix(in srgb, ${roleColor[u.role]} 21%, transparent)` }}>
                    {u.role}
                  </span>
                </td>
                <td className="px-4 py-3 text-xs" style={{ color: "var(--adaptive-secondary, #64748b)" }}>{u.barangay}</td>
                <td className="px-4 py-3 font-data text-xs" style={{ color: "var(--adaptive-muted, #8190a4)" }}>{u.joinedAt}</td>
                <td className="px-4 py-3">
                  <span className="design-badge" style={{ padding:"3px 10px", color: u.status === "Active" ? "var(--adaptive-success, #00e83a)" : "var(--adaptive-muted, #6b7280)" }}>
                    {u.status}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <div className="flex gap-1.5">
                    <button disabled={blocked||loading} onClick={() => { setEditing(u); setShowAdd(true); }} className="font-ui text-xs px-2 py-0.5 transition-opacity hover:opacity-80" style={{ background: "var(--adaptive-surface, #001637)", color: "var(--adaptive-secondary, #64748b)", borderRadius: "3px" }}>Edit</button>
                    <button disabled={blocked||loading||updating !== null || u.id === viewer.id} onClick={() => toggleUser(u)} className="font-ui text-xs px-2 py-0.5 transition-opacity hover:opacity-80 disabled:opacity-30" style={{ background: "rgba(239,68,68,0.1)", color: "var(--adaptive-danger, #ff0000)", borderRadius: "3px" }}>
                      {u.status === "Active" ? "Deactivate" : "Activate"}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          {!loading && !error && filtered.length === 0 && <tr><td colSpan={7} className="px-4 py-8 text-center text-xs" style={{ color: "var(--adaptive-secondary, #64748b)" }}>No users found.</td></tr>}
          </tbody>
        </table>
      </div>

      {showAdd && <AddUserModal invitation={invitation} user={editing} onClose={() => { setShowAdd(false); setEditing(undefined); }} onSave={async (payload) => {
        if(blocked)return;
        if(!editing&&invitation){const {password:discarded,...inviteFields}=payload;void discarded;await accountRequest("invitations","POST",inviteFields);setShowAdd(false);setError("Invitation queued. The account appears after verified acceptance.");return;}
        let saved:Account;
        try{saved = await accountRequest<Account>(editing ? `users/${editing.id}` : "users", editing ? "PATCH" : "POST", {...payload,...(editing?{expected_version:editing.version}:{})});}
        catch(error){if(error instanceof AccountError&&error.status===409){setShowAdd(false);setEditing(undefined);setBlocked(true);setError(error.message+" Stale form and passwords discarded; refresh and review.");return;}throw error;}
        setUsers(items => editing ? items.map(item => item.id === saved.id ? displayUser(saved) : item) : [displayUser(saved), ...items]);
        if (saved.id === viewer.id) { setUser(saved); if (payload.password) window.location.assign("/login"); }
        setShowAdd(false); setEditing(undefined);
      }} />}
    </div>
  );
}
