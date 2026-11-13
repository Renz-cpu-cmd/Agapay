import "server-only";
import {createHmac,randomUUID} from "node:crypto";
import {isIP} from "node:net";
import { cache } from "react";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import type { Account } from "./accounts";

export const sessionCookie = "agapay_session";
const backend = (process.env.AGAPAY_API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

export async function backendRequest(path: string, token?: string, method = "GET", body?: unknown, clientIp?:string, requireStaff=false) {
  const key=process.env.AGAPAY_AUTH_PROXY_KEY;
  const timestamp=String(Math.floor(Date.now()/1000));
  const asserted:Record<string,string>=clientIp&&isIP(clientIp)&&key&&key.length>=32?{"x-agapay-client-ip":clientIp,"x-agapay-client-time":timestamp,"x-agapay-client-signature":createHmac("sha256",key).update(`${timestamp}\n${clientIp}\n${method}\n/api/${path.split("?")[0]}`).digest("hex")}:{};
  return fetch(`${backend}/api/${path}`, {
    method, cache: "no-store", signal: AbortSignal.timeout(10000),
    headers: { "Content-Type": "application/json", "X-Request-ID":randomUUID(), ...(requireStaff?{"X-Agapay-Require-Staff":"1"}:{}), ...asserted, ...(token ? { Authorization: `Bearer ${token}` } : {}) },
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
