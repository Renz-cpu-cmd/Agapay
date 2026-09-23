import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";
import { backendRequest, sessionCookie } from "@/lib/account-server";

type Context = { params: Promise<{ path: string[] }> };
const allowed: Record<string, string[]> = {
  login: ["POST"], setup: ["GET", "POST"], logout: ["POST"], me: ["GET", "PATCH"], users: ["GET", "POST"], sos: ["GET"],
};

function json(data: unknown, status = 200) {
  return NextResponse.json(data, { status, headers: { "Cache-Control": "no-store" } });
}

async function handle(request: NextRequest, context: Context) {
  const path = (await context.params).path.join("/");
  const alertRead = /^alerts(?:\/active|\/\d+(?:\/transitions)?)?$/.test(path);
  const methods = alertRead ? ["GET"] : /^users\/\d+$/.test(path) ? ["PATCH"] : /^sos\/\d+$/.test(path) ? ["GET", "PATCH"] : /^predictions\/[A-Z0-9_-]{3,50}$/.test(path) || path === "monitoring/stations" ? ["GET"] : allowed[path];
  if (!methods?.includes(request.method)) return json({ detail: "Not found." }, 404);
  if (path === "setup") {
    // Setup is a local development feature. Production keeps the CLI bootstrap.
    const loopback = (hostname: string) => ["localhost", "127.0.0.1", "[::1]"].includes(hostname);
    const local = process.env.NODE_ENV === "development" && loopback(new URL(request.url).hostname)
      && loopback(new URL(`http://${request.headers.get("host") ?? "invalid"}`).hostname)
      && loopback(new URL(process.env.AGAPAY_API_URL ?? "http://127.0.0.1:8000").hostname);
    if (!local) return request.method === "GET"
      ? json({ available: false, reason: "Administrator registration is available only in local development." })
      : json({ detail: "Administrator registration is available only in local development." }, 403);
  }
  if (request.method !== "GET") {
    // Next's development server can normalize request.url to localhost even
    // when the browser uses 127.0.0.1. Host preserves the browser's real origin.
    const url = new URL(request.url);
    const origin = process.env.AGAPAY_WEB_ORIGIN ?? `${url.protocol}//${request.headers.get("host") ?? url.host}`;
    if (request.headers.get("origin") !== origin) return json({ detail: "Request origin was not accepted." }, 403);
  }
  const jar = await cookies();
  const token = jar.get(sessionCookie)?.value;
  let body: Record<string, unknown> | undefined;
  if (["POST", "PATCH"].includes(request.method) && path !== "logout") {
    const raw = await request.text();
    if (raw.length > 16384) return json({ detail: "Request is too large." }, 413);
    try { body = JSON.parse(raw); } catch { return json({ detail: "Invalid request." }, 400); }
    if (!body || typeof body !== "object" || Array.isArray(body)) return json({ detail: "Invalid request." }, 400);
  }
  try {
    if (path !== "login" && path !== "logout" && path !== "setup") {
      if (!token) return json({ detail: "Please sign in." }, 401);
      const check = await backendRequest("auth/me", token);
      if (check.status === 401) { jar.delete(sessionCookie); return json({ detail: "Your session has expired. Please sign in again." }, 401); }
      if (!check.ok) return json({ detail: "Account service unavailable." }, 503);
      const user = await check.json();
      if (!["admin", "officer"].includes(user.role)) return json({ detail: "Staff access is required." }, 403);
    }
    let upstreamPath = /^(users|sos|predictions|monitoring|alerts)(\/|$)/.test(path) ? path : `auth/${path}`;
    if (alertRead) {
      const query = new URLSearchParams();
      const keys = path.endsWith("/transitions") ? ["limit", "offset"] : ["station_id", "status", "severity", "limit", "offset"];
      for (const key of keys) {
        const value = request.nextUrl.searchParams.get(key);
        if (value !== null) query.set(key, value);
      }
      if (query.size) upstreamPath += `?${query}`;
    }
    if (path === "sos") {
      const query = new URLSearchParams();
      for (const key of ["status", "limit", "offset"]) {
        const value = request.nextUrl.searchParams.get(key);
        if (value !== null) query.set(key, value);
      }
      if (query.size) upstreamPath += `?${query}`;
    }
    if (path.startsWith("predictions/")) {
      const query = new URLSearchParams();
      for (const key of ["mode", "scenario"]) {
        const value = request.nextUrl.searchParams.get(key);
        if (value !== null) query.set(key, value);
      }
      if (query.size) upstreamPath += `?${query}`;
    }
    if (path === "monitoring/stations") {
      const historyLimit = request.nextUrl.searchParams.get("history_limit");
      if (historyLimit !== null) upstreamPath += `?${new URLSearchParams({ history_limit: historyLimit })}`;
    }
    if (path === "login") body = { ...body, audience: "web" };
    const response = await backendRequest(upstreamPath, token, request.method, body);
    if (path === "logout") {
      if (!response.ok) return json({ detail: "Could not sign out. Please try again." }, 503);
      jar.delete(sessionCookie);
      return new NextResponse(null, { status: 204, headers: { "Cache-Control": "no-store" } });
    }
    const data = await response.json();
    if (!response.ok) {
      if (response.status === 401 && path !== "login") jar.delete(sessionCookie);
      const result = json(data, response.status);
      const retry = response.headers.get("retry-after");
      if (retry) result.headers.set("Retry-After", retry);
      return result;
    }
    if (path === "login" || (path === "setup" && request.method === "POST")) {
      if (token) await backendRequest("auth/logout", token, "POST").catch(() => undefined);
      jar.set(sessionCookie, data.access_token, {
        httpOnly: true, secure: process.env.NODE_ENV === "production", sameSite: "lax", path: "/", expires: new Date(data.expires_at),
      });
      return json({ user: data.user });
    }
    if (path === "me" && body?.password) jar.delete(sessionCookie);
    return json(data, response.status);
  } catch {
    return json({ detail: "Unable to reach the server. Please try again." }, 503);
  }
}

export const GET = handle;
export const POST = handle;
export const PATCH = handle;
