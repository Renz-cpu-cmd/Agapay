"use client";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { accountRequest, type Account } from "@/lib/accounts";

const Context = createContext<{ user: Account; setUser: (user: Account) => void } | null>(null);

export function AccountProvider({ initialUser, children }: { initialUser: Account; children: ReactNode }) {
  const [user, setUser] = useState(initialUser);
  useEffect(() => {
    let active = true;
    async function check() {
      if (document.visibilityState !== "visible") return;
      try {
        const latest = await accountRequest<Account>("me");
        if (active) setUser(latest);
      } catch { /* Actions show network errors; a 401 redirects in accountRequest. */ }
    }
    const timer = setInterval(check, 60000);
    window.addEventListener("focus", check);
    return () => { active = false; clearInterval(timer); window.removeEventListener("focus", check); };
  }, []);
  return <Context.Provider value={{ user, setUser }}>{children}</Context.Provider>;
}

export function useAccount() {
  const value = useContext(Context);
  if (!value) throw new Error("AccountProvider is required");
  return value;
}
