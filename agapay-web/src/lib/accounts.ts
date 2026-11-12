export type Account = {
  id: number;
  name: string;
  email: string;
  phone: string;
  barangay: string;
  role: "admin" | "officer" | "resident";
  is_active: boolean;
  version: number;
  email_verified_at?: string | null;
  created_at: string;
  updated_at: string;
};

export class AccountError extends Error {
  constructor(message:string,public status:number,public current?:Account){super(message);}
}

export async function accountRequest<T>(path: string, method = "GET", body?: unknown, signal?: AbortSignal): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/account/${path}`, {
      method, credentials: "same-origin", cache: "no-store", signal,
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new Error("Unable to connect. Check your connection and try again.");
  }
  const data = response.status === 204 ? null : await response.json();
  if (!response.ok) {
    if (response.status === 401 && !["login","mfa/verify","recovery/request","recovery/complete","capabilities"].includes(path)) window.location.assign("/login");
    const detail = data?.detail;
    const message = Array.isArray(detail) ? detail.map((item: { loc?: string[]; msg: string }) => `${item.loc?.at(-1) ?? "Field"}: ${item.msg}`).join(" ") : typeof detail === "object" ? detail?.message : detail;
    throw new AccountError(typeof message === "string" ? message : "Unable to complete this request. Please try again.",response.status,detail?.current);
  }
  return data as T;
}
