"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export type AppTheme = "light" | "dark";
const storageKey = "agapay-theme";
const ThemeContext = createContext<{ theme: AppTheme; ready: boolean; setTheme: (theme: AppTheme) => void } | null>(null);

// Run before first paint so a saved dark preference does not flash light.
export {themeStartupScript} from "@/lib/theme-startup";

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, updateTheme] = useState<AppTheme>("light");
  const [ready, setReady] = useState(false);
  useEffect(() => {
    updateTheme(document.documentElement.dataset.theme === "dark" ? "dark" : "light");
    setReady(true);
    function sync(event: StorageEvent) {
      if (event.key !== storageKey && event.key !== null) return;
      const next = event.newValue === "dark" ? "dark" : "light";
      document.documentElement.dataset.theme = next;
      updateTheme(next);
    }
    window.addEventListener("storage", sync);
    return () => window.removeEventListener("storage", sync);
  }, []);
  function setTheme(next: AppTheme) {
    document.documentElement.dataset.theme = next;
    updateTheme(next);
    try { localStorage.setItem(storageKey, next); } catch { /* Keep the current session usable when storage is blocked. */ }
  }
  return <ThemeContext.Provider value={{ theme, ready, setTheme }}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) throw new Error("useTheme requires ThemeProvider");
  return context;
}

export function ThemeSelector() {
  const { theme, ready, setTheme } = useTheme();
  return <select aria-label="Theme" className="design-input" disabled={!ready} value={theme} onChange={event => setTheme(event.target.value === "dark" ? "dark" : "light")}><option value="light">Default (Light)</option><option value="dark">Dark</option></select>;
}
