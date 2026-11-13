import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";
import { backendRequest, sessionCookie } from "@/lib/account-server";

type Context = { params: Promise<{ path: string[] }> };
const allowed: Record<string, string[]> = {
  "operations/status":["GET"],"operations/diagnostics":["GET"],"operations/recovery-reviews":["POST"],capabilities:["GET"],"recovery/request":["POST"],"recovery/complete":["POST"],"mfa/verify":["POST"],"mfa/start":["POST"],
  security:["GET"],"security/revoke-session":["POST"],"security/revoke-device":["POST"],"security/revoke-all":["POST"],invitations:["POST"],audit:["GET"],
  preferences:["GET","PATCH"],"preferences/areas":["GET"],
  "official-notices": ["GET", "POST"], "alert-governance/capabilities": ["GET"],
  login: ["POST"], setup: ["GET", "POST"], logout: ["POST"], me: ["GET", "PATCH"], users: ["GET", "POST"], sos: ["GET"],
};

function json(data: unknown, status = 200) {
  return NextResponse.json(data, { status, headers: { "Cache-Control": "no-store" } });
}

async function handle(request: NextRequest, context: Context) {
  const path = (await context.params).path.join("/");
  const publicIdentity=["capabilities","recovery/request","recovery/complete","mfa/verify"].includes(path);
  const deliveryRead=/^notification-deliveries(?:\/\d+)?$/.test(path);
  const deliveryReview=/^notification-deliveries\/\d+\/reconcile$/.test(path);
  const forecastRead=/^(forecast-registry(?:\/[a-f0-9]{64}\/evidence)?|forecast-workspaces\/[A-Z0-9_-]{3,50}|forecast-deployments\/[A-Z0-9_-]{3,50}|forecasts\/[a-f0-9-]{36}|rain-activity\/[A-Z0-9_-]{3,50})$/.test(path);
  const forecastWrite=/^(forecast-registry\/[a-f0-9]{64}\/review|forecast-deployments\/[A-Z0-9_-]{3,50})$/.test(path);
  const historyRead = path === "monitoring/history";
  const stationRead=/^stations\/[A-Z0-9_-]{3,50}\/(operations|workspace|hazard-policy)$/.test(path);
  const ownershipWrite=/^alerts\/\d+\/ownership$/.test(path);
  const stationLifecycle=/^stations\/[A-Z0-9_-]{3,50}\/lifecycle$/.test(path);
  const stationMetadata=/^stations\/[A-Z0-9_-]{3,50}\/metadata$/.test(path);
  const alertRead = /^alerts(?:\/active|\/command-queue|\/\d+(?:\/transitions)?)?$/.test(path);
  const rainRead = /^rain-gauge\/[A-Z0-9_-]{3,50}$/.test(path);
  const hybridProjection = /^hybrid-projections\/[A-Z0-9_-]{3,50}$/.test(path);
  const resourceRead=/^response-resources(?:\/maintenance-context|\/[A-Za-z0-9_-]{3,80}\/revisions)?$/.test(path);
  const resourceReview=/^response-resources\/[A-Za-z0-9_-]{3,80}\/review$/.test(path);
  const resourceMethods=path==="response-resources"?["GET","POST"]:resourceRead?["GET"]:resourceReview?["POST"]:undefined;
  const responseRead = /^sos-response\/(policy|staff|incidents|\d+)$/.test(path);
  const responseAction = /^sos-response\/\d+\/(start|actions)$/.test(path);
  const responseMethods = path==="sos-response/policy"?["GET","PATCH"]:path==="sos-response/incidents"?["GET","POST"]:responseRead?["GET"]:responseAction?["POST"]:undefined;
  const privacyRead=/^privacy\/(notice|cases|admin\/(cases|evidence|access-review|holds\/\d+))$/.test(path);
  const privacyCreate=/^privacy\/(cases|export|admin\/access-review|admin\/cases\/[a-f0-9-]{36}\/application-erasure)$/.test(path);
  const privacyEdit=/^privacy\/admin\/(cases\/[a-f0-9-]{36}|holds\/\d+)$/.test(path);
  const methods = privacyRead&&request.method==='GET'?['GET']:privacyCreate&&request.method==='POST'?['POST']:privacyEdit?['PATCH']:forecastWrite?(request.method==="GET"&&forecastRead?["GET"]:["POST"]):forecastRead?["GET"]:deliveryReview?["POST"]:deliveryRead?["GET"]:resourceMethods ?? responseMethods ?? (stationLifecycle?["POST"]:stationMetadata?["PATCH"]:stationRead?["GET"]:hybridProjection ? ["POST"] : alertRead || rainRead || historyRead ? ["GET"] : /^users\/\d+$/.test(path) ? ["PATCH"] : /^sos\/\d+$/.test(path) ? ["GET", "PATCH"] : /^predictions\/[A-Z0-9_-]{3,50}$/.test(path) || path === "monitoring/stations" ? ["GET"] : allowed[path]);
  if (!(ownershipWrite ? ["POST"] : methods)?.includes(request.method)) return json({ detail: "Not found." }, 404);
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
    if (path !== "login" && path !== "logout" && path !== "setup" && !publicIdentity) {
      if (!token) return json({ detail: "Please sign in." }, 401);

    }
    let upstreamPath = /^(stations|users|sos|sos-response|response-resources|notification-deliveries|privacy|forecast-registry|forecast-workspaces|forecast-deployments|forecasts|rain-activity|operations|predictions|monitoring|alerts|rain-gauge|hybrid-projections|official-notices|alert-governance)(\/|$)/.test(path) ? path : `auth/${path}`;
    if(path.startsWith('privacy/')){
      const query=new URLSearchParams();for(const key of ['after','limit']){const value=request.nextUrl.searchParams.get(key);if(value!==null)query.set(key,value);}if(query.size)upstreamPath+='?'+query;
    }
    if(path==='notification-deliveries'){
      const query=new URLSearchParams();for(const key of ['before_id','limit','state']){const value=request.nextUrl.searchParams.get(key);if(value!==null)query.set(key,value);}if(query.size)upstreamPath+='?'+query;
    }
    if(path.startsWith('forecast-workspaces/')){
      const query=new URLSearchParams();for(const key of ['limit','offset']){const value=request.nextUrl.searchParams.get(key);if(value!==null)query.set(key,value);}if(query.size)upstreamPath+='?'+query;
    }
    if (rainRead) {
      const query = new URLSearchParams();
      for (const key of ["source", "since_id", "anchor_at"]) {
        const value = request.nextUrl.searchParams.get(key);
        if (value !== null) query.set(key, value);
      }
      if (query.size) upstreamPath += `?${query}`;
    }
    if (/^sos-response\/\d+$/.test(path)) {
      const before=request.nextUrl.searchParams.get("before_event_id");if(before!==null)upstreamPath+=`?before_event_id=${encodeURIComponent(before)}`;
    }
    if(/^response-resources\/[A-Za-z0-9_-]{3,80}\/revisions$/.test(path)){
      const query=new URLSearchParams();for(const key of ["limit","offset"]){const value=request.nextUrl.searchParams.get(key);if(value!==null)query.set(key,value);}if(query.size)upstreamPath+=`?${query}`;
    }
    if(path==="response-resources"){
      const query=new URLSearchParams();for(const key of ["kind","mode","area_id","include_drafts","limit","offset"]){const value=request.nextUrl.searchParams.get(key);if(value!==null)query.set(key,value);}if(query.size)upstreamPath+=`?${query}`;
    }
    if (path === "audit") {
      const query=new URLSearchParams();for(const key of ["subject_type","subject_id","limit","offset"]){const value=request.nextUrl.searchParams.get(key);if(value!==null)query.set(key,value);}if(query.size)upstreamPath+=`?${query}`;
    }
    if (path === "official-notices") {
      const query = new URLSearchParams();
      for (const key of ["limit", "offset"]) { const value = request.nextUrl.searchParams.get(key); if (value !== null) query.set(key,value); }
      if (query.size) upstreamPath += `?${query}`;
    }
    if (alertRead) {
      const query = new URLSearchParams();
      const keys = path === "alerts/command-queue" ? ["scope", "limit", "offset"] : path.endsWith("/transitions") ? ["limit", "offset"] : ["station_id", "status", "severity", "limit", "offset"];
      for (const key of keys) {
        const value = request.nextUrl.searchParams.get(key);
        if (value !== null) query.set(key, value);
      }
      if (query.size) upstreamPath += `?${query}`;
    }
    if (/^stations\/[A-Z0-9_-]{3,50}\/workspace$/.test(path)) {
      const query=new URLSearchParams();
      for(const key of ["limit","offset"]){const value=request.nextUrl.searchParams.get(key);if(value!==null)query.set(key,value);}
      if(query.size)upstreamPath+=`?${query}`;
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
    if (historyRead) {
      const query = new URLSearchParams();
      for (const key of ["start_at","end_at","timezone","bucket_seconds","event_id"]) {
        const value=request.nextUrl.searchParams.get(key);if(value!==null)query.set(key,value);
      }
      for(const value of request.nextUrl.searchParams.getAll("station_id"))query.append("station_id",value);
      if(query.size)upstreamPath+=`?${query}`;
    }
    if (path === "monitoring/stations") {
      const historyLimit = request.nextUrl.searchParams.get("history_limit");
      if (historyLimit !== null) upstreamPath += `?${new URLSearchParams({ history_limit: historyLimit })}`;
    }
    if (path === "login") body = { ...body, audience: "web" };
    const sourceHeader=process.env.AGAPAY_TRUSTED_CLIENT_IP_HEADER;
    const clientIp=sourceHeader?request.headers.get(sourceHeader)??undefined:undefined;
    const response = await backendRequest(upstreamPath, token, request.method, body, clientIp, path!=="login"&&path!=="setup"&&!publicIdentity);
    if (path === "logout") {
      if (!response.ok) return json({ detail: "Could not sign out. Please try again." }, 503);
      jar.delete(sessionCookie);
      return new NextResponse(null, { status: 204, headers: { "Cache-Control": "no-store" } });
    }
    const data = await response.json();
    if (!response.ok) {
      if (response.status === 401 && path !== "login" && !publicIdentity) jar.delete(sessionCookie);
      const result = json(data, response.status);
      const correlation=response.headers.get("X-Request-ID");if(correlation)result.headers.set("X-Request-ID",correlation);
      const retry = response.headers.get("retry-after");
      if (retry) result.headers.set("Retry-After", retry);
      return result;
    }
    if ((path === "login" && data.access_token) || path === "mfa/verify" || (path === "setup" && request.method === "POST")) {
      if (token) await backendRequest("auth/logout", token, "POST").catch(() => undefined);
      jar.set(sessionCookie, data.access_token, {
        httpOnly: true, secure: process.env.NODE_ENV === "production", sameSite: "lax", path: "/", expires: new Date(data.expires_at),
      });
      return json({ user: data.user, ...(data.recovery_codes?{recovery_codes:data.recovery_codes}:{}) });
    }
    if (path === "me" && body?.password) jar.delete(sessionCookie);
    const result=json(data,response.status);
    const correlation=response.headers.get("X-Request-ID");if(correlation)result.headers.set("X-Request-ID",correlation);
    return result;
  } catch {
    return json({ detail: "Unable to reach the server. Please try again." }, 503);
  }
}

export const GET = handle;
export const POST = handle;
export const PATCH = handle;
