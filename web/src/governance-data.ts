export type GrantStatus = "REQUESTED" | "ACTIVE" | "REVOKED";
export type ReviewStatus = "REQUESTED" | "APPROVED" | "REJECTED";
export type GrantQueueKind = "support-institution" | "lender";
export type GovernanceGrant = {
  id: string; identity_id: string; role_code: string; scope_type: "PROGRAM" | "PROVIDER";
  scope_id: string; valid_from: string; valid_until: string | null; status: GrantStatus;
  granted_by: string | null; reason_ref: string | null; version: number;
};
export type BenefitLineageReview = {
  id: string; benefit_type: "MONTHLY_PENSION" | "POST_EXIT_SUPPORT"; benefit_record_id: string;
  participant_id: string; program_id: string; participation_episode_id: string;
  evidence_reference: string; reason_reference: string; status: ReviewStatus; requested_by: string;
  reviewed_by: string | null; reviewed_at: string | null; review_reason_reference: string | null; created_at: string;
};
export type QueuePage<T> = { items: T[]; status: string; limit: number; offset: number };
const grantStatuses = new Set<GrantStatus>(["REQUESTED","ACTIVE","REVOKED"]);
const reviewStatuses = new Set<ReviewStatus>(["REQUESTED","APPROVED","REJECTED"]);
export function governanceQueuePath(kind: GrantQueueKind | "benefit-lineage", status: GrantStatus | ReviewStatus, limit=25, offset=0): string {
  const valid = kind === "benefit-lineage" ? reviewStatuses.has(status as ReviewStatus) : grantStatuses.has(status as GrantStatus);
  if (!valid || !Number.isSafeInteger(limit) || limit < 1 || limit > 100 || !Number.isSafeInteger(offset) || offset < 0)
    throw new Error("وضعیت یا محدوده صف راهبری معتبر نیست.");
  const path = kind === "support-institution" ? "/api/v1/admin/support-institution/grants"
    : kind === "lender" ? "/api/v1/admin/lender-access/grants" : "/api/v1/admin/benefit-lineage/reviews";
  return path + "?status=" + status + "&limit=" + limit + "&offset=" + offset;
}
function object(value: unknown): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) throw new Error("ساختار پاسخ راهبری معتبر نیست.");
  return value as Record<string, unknown>;
}
function rows(value: unknown): unknown[] {
  if (!Array.isArray(value)) throw new Error("فهرست صف راهبری معتبر نیست.");
  return value;
}
function isUuid(value: unknown): value is string {
  return typeof value === "string" && /^[a-f\d]{8}-[a-f\d]{4}-[1-8][a-f\d]{3}-[89ab][a-f\d]{3}-[a-f\d]{12}$/i.test(value);
}
function nonEmpty(value: unknown): value is string { return typeof value === "string" && value.trim().length > 0; }
function aware(value: unknown): boolean {
  return typeof value === "string" && /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)$/.test(value) && !Number.isNaN(Date.parse(value));
}
function nullableTime(value: unknown): boolean { return value === null || aware(value); }
function validPage(r: Record<string, unknown>, status: string, limit: number, offset: number): boolean {
  return r.status === status && r.limit === limit && r.offset === offset &&
    Number.isInteger(r.limit) && Number.isInteger(r.offset);
}
export function verifiedGrantPage(raw: unknown, status: GrantStatus, expectedRole: string, scopeType: "PROGRAM" | "PROVIDER", limit: number, offset: number): QueuePage<GovernanceGrant> {
  const r = object(raw);
  if (!validPage(r,status,limit,offset)) throw new Error("صف دسترسی با وضعیت یا صفحه انتخاب‌شده تطابق ندارد.");
  const items = rows(r.items);
  if (items.length > limit) throw new Error("تعداد رکوردهای صف دسترسی از حد صفحه بیشتر است.");
  for (const rawGrant of items) {
    const g = object(rawGrant);
    if (!isUuid(g.id) || !isUuid(g.identity_id) || g.role_code !== expectedRole || g.scope_type !== scopeType ||
      !isUuid(g.scope_id) || !aware(g.valid_from) || !nullableTime(g.valid_until) || g.status !== status ||
      !(g.granted_by === null || isUuid(g.granted_by)) || !(g.reason_ref === null || nonEmpty(g.reason_ref)) ||
      !Number.isInteger(g.version) || (g.version as number) < 1)
      throw new Error("رکورد مجوز دارای دامنه یا lineage نامعتبر است.");
  }
  return r as unknown as QueuePage<GovernanceGrant>;
}
export function verifiedBenefitReviewPage(raw: unknown, status: ReviewStatus, limit: number, offset: number): QueuePage<BenefitLineageReview> {
  const r = object(raw);
  if (!validPage(r,status,limit,offset)) throw new Error("صف بررسی lineage با وضعیت یا صفحه انتخاب‌شده تطابق ندارد.");
  const items = rows(r.items);
  if (items.length > limit) throw new Error("تعداد رکوردهای صف بررسی از حد صفحه بیشتر است.");
  for (const rawReview of items) {
    const item = object(rawReview);
    if (!isUuid(item.id) || !["MONTHLY_PENSION","POST_EXIT_SUPPORT"].includes(String(item.benefit_type)) ||
      !isUuid(item.benefit_record_id) || !isUuid(item.participant_id) || !isUuid(item.program_id) ||
      !isUuid(item.participation_episode_id) || !nonEmpty(item.evidence_reference) ||
      !nonEmpty(item.reason_reference) || item.status !== status || !isUuid(item.requested_by) ||
      !(item.reviewed_by === null || isUuid(item.reviewed_by)) || !nullableTime(item.reviewed_at) ||
      !(item.review_reason_reference === null || nonEmpty(item.review_reason_reference)) || !aware(item.created_at))
      throw new Error("رکورد بررسی lineage ناقص یا ناسازگار است.");
  }
  return r as unknown as QueuePage<BenefitLineageReview>;
}
