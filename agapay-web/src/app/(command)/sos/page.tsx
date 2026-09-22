import { requireStaff } from "@/lib/account-server";
import Screen from "@/components/SOSBeacons";

export default async function Page() { await requireStaff(); return <Screen />; }
