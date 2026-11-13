import type { ReactNode } from "react";
import CommandCenter from "@/components/CommandCenter";
import { requireStaff } from "@/lib/account-server";

export default async function CommandLayout({ children }: { children: ReactNode }) {
  const user = await requireStaff();
  return <CommandCenter user={user}>{children}</CommandCenter>;
}
