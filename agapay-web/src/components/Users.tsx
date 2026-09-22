"use client";

import { useEffect, useState } from "react";
import { FigmaIcon } from "./DesignUI";
import { useDialog } from "@/hooks/useDialog";
import { accountRequest, type Account } from "@/lib/accounts";
import { useAccount } from "@/context/AccountContext";

type User = Account & { status: string; joinedAt: string };
type SaveUser = Pick<Account, "name" | "email" | "phone" | "barangay" | "role"> & { password?: string };
function displayUser(user: Account): User {
  return { ...user, status: user.is_active ? "Active" : "Inactive", joinedAt: new Date(user.created_at).toLocaleDateString("en-PH", { year: "numeric", month: "short", day: "numeric", timeZone: "Asia/Manila" }) };
}

const roleColor: Record<User["role"], string> = {
  admin: "#0ea5e9",
  officer: "#f5df00",
  resident: "#00e83a",
};

function AddUserModal({ onClose, onSave, user }: { onClose: () => void; onSave: (user: SaveUser) => Promise<void>; user?: User }) {
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
      await onSave({ name, email, role: data.get("role") as User["role"], phone: String(data.get("Phone") ?? "").trim(), barangay: String(data.get("barangay") ?? "").trim(), ...(password ? { password } : {}) });
    } catch (error) { setError(error instanceof Error ? error.message : "Unable to save account."); setBusy(false); }
  }
  return (
    <div ref={dialogRef} role="dialog" aria-modal="true" aria-label="User details" tabIndex={-1} className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: "rgba(0,0,0,0.8)" }}>
      <form onSubmit={submit} className="w-96 p-6 flex flex-col gap-4" style={{ background: "#00112e", border: "1px solid #002967", borderRadius: "4px" }}>
        <div className="flex items-center justify-between">
          <h3 className="font-ui font-700 text-sm" style={{ color: "#ffffff" }}>{user ? "Edit User" : "Add User"}</h3>
          <button aria-label="Close dialog" type="button" onClick={onClose} style={{ color: "#8190a4" }}>✕</button>
        </div>
        {error && <p role="alert" className="text-xs text-red-400">{error}</p>}
        {[
          { label: "Full Name", placeholder: "Juan Santos" },
          { label: "Email", placeholder: "j.santos@urdaneta.gov.ph" },
          { label: "Phone", placeholder: "+63 912 345 6789" },
          { label: "Password", placeholder: user ? "Leave blank to keep password" : "At least 12 characters" },
        ].map(({ label, placeholder }) => (
          <div key={label} className="flex flex-col gap-1.5">
            <label htmlFor={`user-${label}`} className="font-ui text-xs tracking-wide" style={{ color: "#8190a4" }}>{label}</label>
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
              style={{ background: "#001434", border: "1px solid #002967", borderRadius: "4px", color: "#ffffff" }}
            />
          </div>
        ))}
        <div className="flex flex-col gap-1.5">
          <label className="font-ui text-xs tracking-wide" style={{ color: "#8190a4" }}>Role</label>
          <select aria-label="Role" name="role" defaultValue={user?.role ?? "officer"} className="px-3 py-2 text-sm outline-none" style={{ background: "#001434", border: "1px solid #002967", borderRadius: "4px", color: "#ffffff" }}>
            <option>officer</option>
            <option>resident</option>
            <option>admin</option>
          </select>
        </div>
        <div className="flex flex-col gap-1.5">
          <label className="font-ui text-xs tracking-wide" style={{ color: "#8190a4" }}>Barangay</label>
          <input required aria-label="Barangay" name="barangay" defaultValue={user?.barangay ?? ""} placeholder="San Vicente" className="px-3 py-2 text-sm outline-none" style={{ background: "#001434", border: "1px solid #002967", borderRadius: "4px", color: "#ffffff" }}/>
        </div>
        <div className="flex gap-3 mt-2">
          <button type="button" onClick={onClose} className="flex-1 py-2 font-ui text-xs font-700" style={{ background: "#001637", color: "#64748b", borderRadius: "4px" }}>CANCEL</button>
          <button disabled={busy} type="submit" className="flex-1 py-2 font-ui text-xs font-700 hover:opacity-80 disabled:opacity-50" style={{ background: "#0ea5e9", color: "#fff", borderRadius: "4px" }}>{busy ? "SAVING..." : user ? "SAVE CHANGES" : "CREATE USER"}</button>
        </div>
      </form>
    </div>
  );
}

export default function Users() {
  const [users, setUsers] = useState<User[]>([]);
  const { user: viewer, setUser } = useAccount();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [updating, setUpdating] = useState<number | null>(null);
  useEffect(() => {
    let active = true;
    accountRequest<Account[]>("users").then(data => { if (active) setUsers(data.map(displayUser)); })
      .catch(error => { if (active) setError(error.message); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);
  async function toggleUser(user: User) {
    setUpdating(user.id); setError("");
    try {
      const saved = await accountRequest<Account>(`users/${user.id}`, "PATCH", { is_active: !user.is_active });
      setUsers(items => items.map(item => item.id === saved.id ? displayUser(saved) : item));
    } catch (error) { setError(error instanceof Error ? error.message : "Unable to update account."); }
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
      {error && <p role="alert" className="text-xs text-red-400">{error} <button onClick={() => window.location.reload()} className="underline">Retry</button></p>}
      {loading && <p role="status" className="text-xs text-slate-400">Loading accounts...</p>}
      {/* Top row */}
      <div className="flex items-center justify-between">
        <div className="flex gap-3">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            aria-label="Search users" placeholder="Search users..."
            className="px-3 py-1.5 text-xs outline-none w-52"
            style={{ background: "#00112e", border: "1px solid #002967", borderRadius: "4px", color: "#ffffff" }}
          />
          <select
            aria-label="User role filter" value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value)}
            className="px-3 py-1.5 text-xs outline-none"
            style={{ background: "#00112e", border: "1px solid #002967", borderRadius: "4px", color: "#64748b" }}
          >
            {["All","admin","officer","resident"].map(o => <option key={o}>{o}</option>)}
          </select>
        </div>
        <button
          onClick={() => { setEditing(undefined); setShowAdd(true); }}
          className="flex items-center gap-2 font-ui text-xs font-700 px-4 py-1.5 transition-opacity hover:opacity-80"
          style={{ background: "#0ea5e9", color: "#fff", borderRadius: "4px" }}
        >
          + Add User
        </button>
      </div>

      {/* Summary by role */}
      <div className="card-grid grid-cols-3">
        {(["admin","officer","resident"] as const).map((role) => (
          <div key={role} className="p-3 flex items-center gap-3" style={{ background: "#00112e", border: "1px solid #002967", borderRadius: "4px" }}>
            <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 font-ui font-bold text-xs"
              style={{ background: `${roleColor[role]}18`, color: roleColor[role] }}>
              {users.filter(u=>u.role===role).length}
            </div>
            <div>
              <p className="font-ui font-700 text-xs capitalize" style={{ color: roleColor[role] }}>{role}s</p>
              <p className="text-xs" style={{ color: "#64748b" }}>{users.filter(u=>u.role===role && u.status==="Active").length} active</p>
            </div>
          </div>
        ))}
      </div>

      {/* Table */}
      <div style={{ background: "#00112e", border: "1px solid #002967", borderRadius: "4px", overflow: "hidden" }}>
        <table className="w-full">
          <thead>
            <tr style={{ borderBottom: "1px solid #002967" }}>
              {["Name","Email","Role","Barangay","Joined","Status","Action"].map(h => (
                <th key={h} className="text-left px-4 py-2.5 font-ui font-700 text-xs tracking-wide" style={{ color: "#8190a4", letterSpacing: "0.1em" }}>
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
                    <span className="font-ui text-xs font-600" style={{ color: "#ffffff" }}>{u.name}</span>
                  </div>
                </td>
                <td className="px-4 py-3 font-data text-xs" style={{ color: "#8190a4" }}>{u.email}</td>
                <td className="px-4 py-3">
                  <span className="font-ui font-700 text-xs px-2 py-0.5 rounded-sm capitalize"
                    style={{ background: `${roleColor[u.role]}18`, color: roleColor[u.role], border: `1px solid ${roleColor[u.role]}35` }}>
                    {u.role}
                  </span>
                </td>
                <td className="px-4 py-3 text-xs" style={{ color: "#64748b" }}>{u.barangay}</td>
                <td className="px-4 py-3 font-data text-xs" style={{ color: "#8190a4" }}>{u.joinedAt}</td>
                <td className="px-4 py-3">
                  <span className="design-badge" style={{ padding:"3px 10px", color: u.status === "Active" ? "#00e83a" : "#6b7280" }}>
                    {u.status}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <div className="flex gap-1.5">
                    <button onClick={() => { setEditing(u); setShowAdd(true); }} className="font-ui text-xs px-2 py-0.5 transition-opacity hover:opacity-80" style={{ background: "#001637", color: "#64748b", borderRadius: "3px" }}>Edit</button>
                    <button disabled={updating !== null || u.id === viewer.id} onClick={() => toggleUser(u)} className="font-ui text-xs px-2 py-0.5 transition-opacity hover:opacity-80 disabled:opacity-30" style={{ background: "rgba(239,68,68,0.1)", color: "#ff0000", borderRadius: "3px" }}>
                      {u.status === "Active" ? "Deactivate" : "Activate"}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          {!loading && !error && filtered.length === 0 && <tr><td colSpan={7} className="px-4 py-8 text-center text-xs" style={{ color: "#64748b" }}>No users found.</td></tr>}
          </tbody>
        </table>
      </div>

      {showAdd && <AddUserModal user={editing} onClose={() => { setShowAdd(false); setEditing(undefined); }} onSave={async (payload) => {
        const saved = await accountRequest<Account>(editing ? `users/${editing.id}` : "users", editing ? "PATCH" : "POST", payload);
        setUsers(items => editing ? items.map(item => item.id === saved.id ? displayUser(saved) : item) : [displayUser(saved), ...items]);
        if (saved.id === viewer.id) { setUser(saved); if (payload.password) window.location.assign("/login"); }
        setShowAdd(false); setEditing(undefined);
      }} />}
    </div>
  );
}
