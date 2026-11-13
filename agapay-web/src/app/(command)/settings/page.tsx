import Profile from "@/components/Profile";
import { requireStaff } from "@/lib/account-server";
export default async function SettingsPage() { await requireStaff(); return <Profile />; }
