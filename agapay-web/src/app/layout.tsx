import type { Metadata } from "next";
import type { ReactNode } from "react";
import "../index.css";
import { ThemeProvider, themeStartupScript } from "@/context/ThemeContext";

export const metadata: Metadata = {
  title: "AGAPAY | Disaster Monitoring Center",
  description: "AGAPAY LGU Command Center for station monitoring, flood alerts, and SOS response.",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return <html lang="en" data-theme="light" suppressHydrationWarning><head><script dangerouslySetInnerHTML={{ __html: themeStartupScript }}/></head><body><ThemeProvider>{children}</ThemeProvider></body></html>;
}
