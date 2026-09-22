import { requireStaff } from "@/lib/account-server";
import { notFound } from "next/navigation";
import Stations from "@/components/Stations";
import { stations } from "@/data/mockData";

export default async function StationPage({ params }: { params: Promise<{ id: string }> }) {
  await requireStaff();
  const { id } = await params;
  if (!stations.some((station) => station.id === id)) notFound();
  return <Stations initialStationId={id} />;
}
