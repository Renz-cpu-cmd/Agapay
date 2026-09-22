"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { accountRequest } from "@/lib/accounts";
import type { SosPage, SosRequest, SosStatus } from "@/lib/sos";

type State = {
  page: SosPage | null; filter: SosStatus | "ALL"; setFilter: (filter: SosStatus | "ALL") => void;
  error: string; syncedAt: string | null; loading: boolean; refresh: () => Promise<void>;
  loadMore: () => void; update: (id: number, status: SosStatus, note: string) => Promise<SosRequest>;
};
const Context = createContext<State | null>(null);

export function SosProvider({ children }: { children: ReactNode }) {
  const [page, setPage] = useState<SosPage | null>(null);
  const [filter, setFilterValue] = useState<SosStatus | "ALL">("ALL");
  const [size, setSize] = useState(50);
  const [error, setError] = useState("");
  const [syncedAt, setSyncedAt] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const generation = useRef(0);
  const mounted = useRef(false);
  const refresh = useCallback(async () => {
    const ticket = ++generation.current;
    setLoading(true);
    try {
      // Read in bounded pages. All counts are computed by the API, not by the visible rows.
      const query = filter === "ALL" ? "" : `&status=${filter}`;
      const pages: SosPage[] = [];
      for (let offset = 0; offset < size; offset += 50) {
        const next = await accountRequest<SosPage>(`sos?limit=50&offset=${offset}${query}`);
        if (ticket !== generation.current || !mounted.current) return;
        pages.push(next);
        if (offset + 50 >= next.total) break;
      }
      setPage({ ...pages[0], items: pages.flatMap((p) => p.items).filter((item, i, all) => all.findIndex((v) => v.id === item.id) === i) });
      setError(""); setSyncedAt(new Date().toISOString());
    } catch (e) {
      if (mounted.current && ticket === generation.current) setError(e instanceof Error ? e.message : "Unable to refresh SOS requests.");
    } finally {
      if (mounted.current && ticket === generation.current) setLoading(false);
    }
  }, [filter, size]);
  useEffect(() => {
    mounted.current = true;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      await refresh();
      if (!stopped) timer = setTimeout(poll, 5000);
    }
    void poll();
    return () => { stopped = true; mounted.current = false; ++generation.current; clearTimeout(timer); };
  }, [refresh]);
  async function update(id: number, status: SosStatus, note: string) {
    ++generation.current;
    const item = await accountRequest<SosRequest>(`sos/${id}`, "PATCH", { status, resolution_note: note });
    ++generation.current;
    if (mounted.current) {
      setPage((old) => old && { ...old, items: old.items.map((v) => v.id === id ? item : v) });
      await refresh();
    }
    return item;
  }
  function setFilter(value: SosStatus | "ALL") {
    if (value === filter) return;
    ++generation.current; setPage((old) => old && { ...old, items: [] }); setFilterValue(value); setSize(50);
  }
  return <Context.Provider value={{ page, filter, setFilter, error, syncedAt, loading, refresh, loadMore: () => setSize((n) => n + 50), update }}>{children}</Context.Provider>;
}
export function useSos() {
  const value = useContext(Context);
  if (!value) throw new Error("useSos requires SosProvider");
  return value;
}
