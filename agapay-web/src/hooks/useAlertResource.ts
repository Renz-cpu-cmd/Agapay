"use client";

import { useEffect, useState } from "react";
import { accountRequest } from "@/lib/accounts";

// One request at a time; schedule the next poll only after settlement. A new
// query/unmount aborts the old request, and old responses cannot overwrite it.
export function useAlertResource<T>(path: string) {
  const [state, setState] = useState<{ path: string; data: T | null; error: boolean; loading: boolean }>({ path, data: null, error: false, loading: true });
  useEffect(() => {
    let disposed = false;
    let inFlight = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let controller: AbortController | undefined;
    async function read() {
      if (disposed || inFlight || document.hidden) return;
      clearTimeout(timer);
      inFlight = true;
      controller = new AbortController();
      const timeout = setTimeout(() => controller?.abort(), 25000);
      try {
        const data = await accountRequest<T>(path, "GET", undefined, controller.signal);
        if (!disposed) setState({ path, data, error: false, loading: false });
      } catch {
        // Clear stale results explicitly; an outage is never an empty/safe state.
        if (!disposed) setState({ path, data: null, error: true, loading: false });
      } finally {
        clearTimeout(timeout);
        inFlight = false;
        if (!disposed && !document.hidden) timer = setTimeout(read, 5000);
      }
    }
    function visibilityChanged() {
      clearTimeout(timer);
      if (!document.hidden) void read();
    }
    void read();
    document.addEventListener("visibilitychange", visibilityChanged);
    return () => {
      disposed = true;
      clearTimeout(timer);
      controller?.abort();
      document.removeEventListener("visibilitychange", visibilityChanged);
    };
  }, [path]);
  return state.path === path ? state : { data: null, error: false, loading: true };
}
