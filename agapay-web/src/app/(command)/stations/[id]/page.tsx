import { requireStaff } from "@/lib/account-server";
import { notFound } from "next/navigation";
import Stations from "@/components/Stations";

export default async function StationPage({ params }: { params: Promise<{ id: string }> }) {
  await requireStaff();
  const { id } = await params;
  if (!/^[A-Z0-9_-]{3,50}$/.test(id)) notFound();
  return <Stations initialStationId={id} />;
}
