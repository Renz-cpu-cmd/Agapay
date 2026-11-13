import { operationalVocabulary } from "./operational-vocabulary";

export interface OfficialNotice {
  id: string; authority_id: string; issuer_name: string; authority_class: "app_operator" | "public_authority";
  area_ids: string[]; area_names: string[]; message_type: "Alert" | "Update" | "Cancel";
  category: "advisory" | "action"; status: "Actual" | "Exercise" | "Test";
  urgency: string; severity: string; certainty: string; headline: string; instruction: string; reason: string;
  sent_at: string; effective_at: string; expires_at: string; reference_id: string | null;
  lifecycle: string; superseded_by: string | null;
}
export function noticeLifecycle(notice: OfficialNotice, nowMs: number): string {
  if (notice.superseded_by) return "superseded";
  if (notice.message_type === "Cancel") return "cancelled";
  const effective = Date.parse(notice.effective_at), expires = Date.parse(notice.expires_at);
  if (!Number.isFinite(effective) || !Number.isFinite(expires)) return "unavailable";
  return nowMs >= expires ? "expired" : nowMs < effective ? "scheduled" : "effective";
}
export function noticeKind(notice: Pick<OfficialNotice, "authority_class" | "category">) {
  return notice.authority_class === "app_operator" ? "App advisory" : notice.authority_class === "public_authority"
    ? notice.category === "action" ? "Authority-issued action" : operationalVocabulary.officialAdvisory : "Unconfirmed notice";
}

export function parseNoticePage(value: unknown): OfficialNotice[] {
  if (!value || typeof value !== "object" || !Array.isArray((value as {items?:unknown}).items)) throw new Error("Invalid notice page");
  return (value as {items:unknown[]}).items.map(item => {
    if (!item || typeof item !== "object") throw new Error("Invalid notice");
    const notice = item as OfficialNotice;
    const strings: (keyof OfficialNotice)[] = ["id","authority_id","issuer_name","headline","instruction","sent_at","effective_at","expires_at","urgency","severity","certainty"];
    if (strings.some(key => typeof notice[key] !== "string" || !notice[key])
      || !["app_operator","public_authority"].includes(notice.authority_class)
      || !["Actual","Test","Exercise"].includes(notice.status)
      || !["Alert","Update","Cancel"].includes(notice.message_type)
      || !["advisory","action"].includes(notice.category)
      || !Array.isArray(notice.area_ids) || !notice.area_ids.length || notice.area_ids.some(id => typeof id !== "string" || !id)
      || !Array.isArray(notice.area_names) || notice.area_names.length !== notice.area_ids.length || notice.area_names.some(name => typeof name !== "string" || !name)
      || ![notice.sent_at,notice.effective_at,notice.expires_at].every(at=>Number.isFinite(Date.parse(at)))
      || Date.parse(notice.expires_at)<=Date.parse(notice.effective_at)
      || (notice.message_type!=="Alert" && !notice.reference_id)
      || (notice.authority_class==="app_operator" && notice.category==="action" && notice.status==="Actual")) throw new Error("Incomplete notice issuer or lifecycle");
    return notice;
  });
}
