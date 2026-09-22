export type Account = {
  id: number;
  name: string;
  email: string;
  phone: string;
  barangay: string;
  role: "admin" | "officer" | "resident";
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export async function accountRequest<T>(path: string, method = "GET", body?: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/account/${path}`, {
      method, credentials: "same-origin", cache: "no-store",
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new Error("Unable to connect. Check your connection and try again.");
  }
  const data = response.status === 204 ? null : await response.json();
  if (!response.ok) {
    if (response.status === 401 && path !== "login") window.location.assign("/login");
    const detail = data?.detail;
    const message = Array.isArray(detail) ? detail.map((item: { loc?: string[]; msg: string }) => `${item.loc?.at(-1) ?? "Field"}: ${item.msg}`).join(" ") : detail;
    throw new Error(typeof message === "string" ? message : "Unable to complete this request. Please try again.");
  }
  return data as T;
}
