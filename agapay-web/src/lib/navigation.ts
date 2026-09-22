export const pagePaths = {
  dashboard: "/dashboard",
  stations: "/stations",
  alerts: "/alerts",
  sos: "/sos",
  analytics: "/analytics",
  health: "/system-health",
  users: "/users",
  settings: "/settings",
} as const;

export type Page = keyof typeof pagePaths;

export function pageFromPath(pathname: string): Page {
  return (Object.keys(pagePaths) as Page[]).find((page) =>
    pathname === pagePaths[page] || pathname.startsWith(`${pagePaths[page]}/`)
  ) ?? "dashboard";
}
