"use client";
import { useRouter } from "next/navigation";
import Dashboard from "./Dashboard";
export default function DashboardScreen() {
  const router = useRouter();
  return <Dashboard onViewStation={id => router.push(`/stations/${encodeURIComponent(id)}`)} />;
}
