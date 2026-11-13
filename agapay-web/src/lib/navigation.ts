export const pagePaths = {
  dashboard: "/dashboard",
  stations: "/stations",
  resources: "/response-resources",
  alerts: "/alerts",
  sos: "/sos",
  analytics: "/analytics",
  forecasts: "/forecasts",
  health: "/system-health",
  users: "/users",
  settings: "/settings",
  mlConfiguration: "/ml-configuration",
  mlEvaluation: "/ml-evaluation",
} as const;

export type Page = keyof typeof pagePaths;

export function navigationGroup(page: Page): Page {
  return page === "mlEvaluation" || page === "forecasts" ? "mlConfiguration" : page;
}

export function pageFromPath(pathname: string): Page {
  return (Object.keys(pagePaths) as Page[]).find((page) =>
    pathname === pagePaths[page] || pathname.startsWith(`${pagePaths[page]}/`)
  ) ?? "dashboard";
}
