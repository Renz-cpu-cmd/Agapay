import { requireStaff } from "@/lib/account-server";
import Screen from "@/components/SystemHealth";

export default async function Page() { await requireStaff(); return <Screen />; }
