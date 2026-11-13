import { requireStaff } from "@/lib/account-server";
import Screen from "@/components/Users";

export default async function Page() { await requireStaff(true); return <Screen />; }
