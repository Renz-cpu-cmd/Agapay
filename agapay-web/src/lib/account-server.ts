import "server-only";
import { cache } from "react";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import type { Account } from "./accounts";

export const sessionCookie = "agapay_session";
const backend = (process.env.AGAPAY_API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

export async function backendRequest(path: string, token?: string, method = "GET", body?: unknown) {
  return fetch(`${backend}/api/${path}`, {
    method, cache: "no-store", signal: AbortSignal.timeout(10000),
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

export const getAccount = cache(async (): Promise<Account | null> => {
  const token = (await cookies()).get(sessionCookie)?.value;
  if (!token) return null;
  const response = await backendRequest("auth/me", token);
  if (response.status === 401 || response.status === 403) return null;
  if (!response.ok) throw new Error("The account service is unavailable. Please try again.");
  return response.json();
});

export async function requireStaff(adminOnly = false): Promise<Account> {
  const user = await getAccount();
  if (!user || !["admin", "officer"].includes(user.role)) redirect("/login");
  if (adminOnly && user.role !== "admin") redirect("/dashboard");
  return user;
}
