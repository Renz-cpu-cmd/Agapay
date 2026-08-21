import type { Metadata } from 'next';
import './globals.css';
import { DashboardProvider } from '@/context/DashboardContext';

export const metadata: Metadata = {
  title: 'AGAPAY | Emergency Flood & Disaster Early-Warning Command Dashboard',
  description: 'Enterprise emergency operations and sensor telemetry dashboard for LGU officers and disaster responders.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <DashboardProvider>{children}</DashboardProvider>
      </body>
    </html>
  );
}
