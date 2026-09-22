import { requireStaff } from "@/lib/account-server";
import DashboardScreen from "@/components/DashboardScreen";
export default async function DashboardPage() {
  await requireStaff();
  return <DashboardScreen />;
}
