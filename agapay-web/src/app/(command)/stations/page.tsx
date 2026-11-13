import { requireStaff } from "@/lib/account-server";
import Stations from "@/components/Stations";

export default async function StationsPage() {
  await requireStaff();
  return <Stations />;
}
