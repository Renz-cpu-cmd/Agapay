import type { Metadata } from "next";
import type { ReactNode } from "react";
import "../index.css";
import "../accessibility.css";
import { ThemeProvider } from "@/context/ThemeContext";

export const metadata: Metadata = {
  title: "AGAPAY | Disaster Monitoring Center",
  description: "AGAPAY LGU Command Center for station monitoring, flood alerts, and SOS response.",
  robots: { index: false, follow: false },
};

import {headers} from "next/headers";
import {themeStartupScript} from "@/lib/theme-startup";

export default async function RootLayout({ children }: { children: ReactNode }) {
  const nonce=(await headers()).get("x-nonce")??undefined;
  return <html lang="en" data-theme="light" suppressHydrationWarning><head><style nonce={nonce}>{":root{}"}</style><script nonce={nonce} dangerouslySetInnerHTML={{ __html: themeStartupScript }}/></head><body><ThemeProvider>{children}</ThemeProvider></body></html>;
}
