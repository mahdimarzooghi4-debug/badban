import type { GrantQueueKind } from "./governance-data";

const uuidPattern = /^[a-f\d]{8}-[a-f\d]{4}-[1-8][a-f\d]{3}-[89ab][a-f\d]{3}-[a-f\d]{12}$/i;
export type GrantAction = "approve" | "revoke";
export type GrantRequestDraft = {
  identityId: string;
  scopeId: string;
  validFrom: string;
  validUntil: string;
  reasonReference: string;
};
function uuid(value: string, label: string): string {
  const normalized = value.trim();
  if (!uuidPattern.test(normalized)) throw new Error(label + " باید یک شناسه UUID معتبر باشد.");
  return normalized.toLowerCase();
}
function iso(value: string, label: string): number {
  if (!value.trim()) throw new Error(label + " الزامی است.");
  const parsed = new Date(value);
  const timestamp = parsed.getTime();
  if (!Number.isFinite(timestamp)) throw new Error(label + " معتبر نیست.");
  return timestamp;
}
export function grantRequestPath(kind: GrantQueueKind): string {
  if (kind === "support-institution") return "/api/v1/admin/support-institution/grants";
  if (kind === "lender") return "/api/v1/admin/lender-access/grants";
  throw new Error("نوع مجوز معتبر نیست.");
}
export function buildGrantRequest(kind: GrantQueueKind, draft: GrantRequestDraft): Record<string, string | null> {
  const identityId = uuid(draft.identityId, "شناسه هویت");
  const scopeId = uuid(draft.scopeId, kind === "support-institution" ? "شناسه برنامه" : "شناسه تأمین‌کننده");
  const validFrom = iso(draft.validFrom, "زمان شروع");
  const validUntil = draft.validUntil.trim() ? iso(draft.validUntil, "زمان پایان") : null;
  if (validUntil !== null && validUntil <= validFrom) throw new Error("زمان پایان باید بعد از زمان شروع باشد.");
  const reason = draft.reasonReference.trim();
  if (!reason || reason.length > 255) throw new Error("مرجع دلیل باید بین ۱ تا ۲۵۵ نویسه باشد.");
  const shared = {
    identity_id: identityId,
    valid_from: new Date(validFrom).toISOString(),
    valid_until: validUntil === null ? null : new Date(validUntil).toISOString(),
    reason_reference: reason,
  };
  return kind === "support-institution"
    ? { ...shared, program_id: scopeId }
    : { ...shared, provider_id: scopeId };
}
export function grantMutationPath(kind: GrantQueueKind, grantId: string, action: GrantAction): string {
  const base = grantRequestPath(kind) + "/" + uuid(grantId, "شناسه مجوز");
  if (action === "approve") return base + "/approve";
  if (action === "revoke") return base + "/revoke";
  throw new Error("عملیات مجوز معتبر نیست.");
}
export function buildGrantRevokeBody(reasonReference: string): { reason_reference: string } {
  const reason = reasonReference.trim();
  if (!reason || reason.length > 255) throw new Error("دلیل لغو باید بین ۱ تا ۲۵۵ نویسه باشد.");
  return { reason_reference: reason };
}
