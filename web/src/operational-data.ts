/**
 * Read-only, bounded API contracts for Badban operational workspaces.
 * Backend authorization remains authoritative; these checks reject mismatched responses.
 */
export type ServiceCode = "LOAN_GUARANTEE" | "MONTHLY_PENSION" | "POST_EXIT_SUPPORT";
export interface AdminWorkspaceAccess {
  workspace_code: string; scope_type: string; scope_id: string | null;
  service_code: string | null; role_codes: string[]; capabilities: string[];
}
const uuidPattern = /^[a-f\d]{8}-[a-f\d]{4}-[1-8][a-f\d]{3}-[89ab][a-f\d]{3}-[a-f\d]{12}$/i;
const services = new Set<ServiceCode>(["LOAN_GUARANTEE", "MONTHLY_PENSION", "POST_EXIT_SUPPORT"]);
export function requireUuid(value: string): string {
  if (!uuidPattern.test(value)) throw new Error("شناسه پرونده معتبر نیست.");
  return value.toLowerCase();
}
export function institutionCasePath(programId: string, participantId: string, episodeId: string): string {
  return "/api/v1/support-institution/programs/" + requireUuid(programId) + "/beneficiaries/" +
    requireUuid(participantId) + "/episodes/" + requireUuid(episodeId) + "/financial-case";
}
export function adminServiceQueuePath(code: ServiceCode, limit = 25, offset = 0): string {
  if (!services.has(code) || !Number.isSafeInteger(limit) || limit < 1 || limit > 100 ||
    !Number.isSafeInteger(offset) || offset < 0) throw new Error("کد خدمت یا محدوده صفحه‌بندی معتبر نیست.");
  return "/api/v1/admin/service-operations/" + code + "/applicant-requests?limit=" + limit + "&offset=" + offset;
}
export function allowedAdminServices(items: AdminWorkspaceAccess[]): ServiceCode[] {
  const found: ServiceCode[] = [];
  for (const item of items) {
    if (item.workspace_code !== "ADMIN_SERVICE_OPERATIONS" || item.scope_type !== "SERVICE" ||
      !item.scope_id || !uuidPattern.test(item.scope_id) || !item.service_code ||
      !services.has(item.service_code as ServiceCode) ||
      !Array.isArray(item.capabilities) || !item.capabilities.includes("READ_APPLICANT_SERVICE_REQUESTS") ||
      !Array.isArray(item.role_codes) || item.role_codes.length === 0) continue;
    const code = item.service_code as ServiceCode;
    if (!found.includes(code)) found.push(code);
  }
  return found;
}
export function serviceLabel(code: ServiceCode): string {
  const labels: Record<ServiceCode, string> = {
    LOAN_GUARANTEE: "ضمانت وام", MONTHLY_PENSION: "مستمری ماهانه", POST_EXIT_SUPPORT: "آینده مالی",
  };
  return labels[code];
}
export function valueOrUnavailable(value: string | number | null | undefined): string {
  return value === null || value === undefined || value === "" ? "اطلاعات موجود نیست" : String(value);
}
export interface InstitutionFinancialCase {
  program_id: string; participant_id: string; episode_id: string;
  assets: Array<{ id: string; asset_code: string; asset_name: string; ownership_funding_type: string;
    quantity: string; unit_code: string; lifecycle_status: string; valuation_observations: Array<{
      id: string; source_name: string; source_reference: string; source_version_reference: string | null;
      observed_at: string; freshness_status: string; valuation_currency: string;
      unit_price: string; gross_market_value: string; valid_until: string | null;
    }> }>;
  guarantees: Array<{ id: string; provider_id: string; state: string; requested_principal: string;
    reserved_guarantee_amount: string | null; issued_guarantee_amount: string | null;
    current_guarantee_exposure: string; guarantee_mode: string; currency: string;
    loan_state: string | null; outstanding_principal: string | null; loan_currency: string | null;
    last_synced_at: string | null; reconciliation_status: string | null }>;
  monthly_pension_entitlements: Array<{ id: string; period_reference: string; amount: string;
    currency: string; lifecycle_status: string; approved_at: string | null }>;
  post_exit_support_cases: Array<{ id: string; exit_at: string; support_start_at: string;
    duration_months: number; lifecycle_status: string; entitlements: Array<{ id: string;
      period_sequence: number; period_reference: string; period_at: string; amount: string;
      currency: string; lifecycle_status: string; approved_at: string | null }> }>;
  program_return_allocations: Array<{ currency: string; amount: string }>;
}
export interface IntakeRequest {
  id: string; participant_id: string; service_code: ServiceCode; status: "RECEIVED"; submitted_at: string;
}
export interface IntakePage {
  service_code: ServiceCode; observed_at: string; items: IntakeRequest[]; limit: number; offset: number;
}
function record(value: unknown): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) throw new Error("ساختار پاسخ سرویس معتبر نیست.");
  return value as Record<string, unknown>;
}
function arr(value: unknown, label: string): unknown[] {
  if (!Array.isArray(value)) throw new Error("فهرست " + label + " در پاسخ معتبر نیست.");
  return value;
}
function nonEmpty(value: unknown): value is string { return typeof value === "string" && value.trim().length > 0; }
function uuid(value: unknown): boolean { return typeof value === "string" && uuidPattern.test(value); }
function decimal(value: unknown): value is string {
  return typeof value === "string" && /^-?(?:0|[1-9]\d*)(?:\.\d+)?$/.test(value);
}
function nullableDecimal(value: unknown): boolean { return value === null || decimal(value); }
function currency(value: unknown): boolean { return typeof value === "string" && /^[A-Z]{3,8}$/.test(value); }
function aware(value: unknown): boolean {
  return typeof value === "string" && /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)$/.test(value)
    && !Number.isNaN(Date.parse(value));
}
function page(r: Record<string, unknown>): boolean {
  return Number.isInteger(r.limit) && (r.limit as number) >= 1 && (r.limit as number) <= 100 &&
    Number.isInteger(r.offset) && (r.offset as number) >= 0;
}
function matches(received: unknown, expected: string): boolean {
  return typeof received === "string" && received.toLowerCase() === requireUuid(expected);
}
function nullableTime(value: unknown): boolean { return value === null || aware(value); }
function checkMoney(value: unknown, currencyCode: unknown): boolean {
  return value === null || (decimal(value) && currency(currencyCode));
}
export function verifiedInstitutionCase(raw: unknown, programId: string, participantId: string, episodeId: string): InstitutionFinancialCase {
  const r = record(raw);
  if (!matches(r.program_id, programId) || !matches(r.participant_id, participantId) || !matches(r.episode_id, episodeId))
    throw new Error("محدوده پرونده مالی با برنامه یا فرد انتخاب‌شده تطابق ندارد.");
  const assets = arr(r.assets, "دارایی‌ها"), guarantees = arr(r.guarantees, "ضمانت‌ها");
  const pensions = arr(r.monthly_pension_entitlements, "مستمری‌ها");
  const cases = arr(r.post_exit_support_cases, "پرونده‌های پس از خروج");
  const returns = arr(r.program_return_allocations, "بازده برنامه");
  for (const rawAsset of assets) {
    const a = record(rawAsset);
    if (!uuid(a.id) || !nonEmpty(a.asset_code) || !nonEmpty(a.asset_name) || !nonEmpty(a.ownership_funding_type) ||
      !decimal(a.quantity) || !nonEmpty(a.unit_code) || !nonEmpty(a.lifecycle_status))
      throw new Error("دارایی پرونده فاقد مقدار یا مرجع معتبر است.");
    for (const rawValuation of arr(a.valuation_observations, "مشاهدات ارزش‌گذاری")) {
      const v = record(rawValuation);
      if (!uuid(v.id) || !nonEmpty(v.source_name) || !nonEmpty(v.source_reference) ||
        !(v.source_version_reference === null || nonEmpty(v.source_version_reference)) || !aware(v.observed_at) ||
        !nonEmpty(v.freshness_status) || !currency(v.valuation_currency) || !decimal(v.unit_price) ||
        !decimal(v.gross_market_value) || !nullableTime(v.valid_until))
        throw new Error("مشاهده ارزش‌گذاری دارایی معتبر نیست.");
    }
  }
  for (const rawGuarantee of guarantees) {
    const g = record(rawGuarantee);
    if (!uuid(g.id) || !uuid(g.provider_id) || !nonEmpty(g.state) || !decimal(g.requested_principal) ||
      !nullableDecimal(g.reserved_guarantee_amount) || !nullableDecimal(g.issued_guarantee_amount) ||
      !decimal(g.current_guarantee_exposure) || !nonEmpty(g.guarantee_mode) || !currency(g.currency) ||
      !(g.loan_state === null || nonEmpty(g.loan_state)) || !checkMoney(g.outstanding_principal, g.loan_currency) ||
      !nullableTime(g.last_synced_at) || !(g.reconciliation_status === null || nonEmpty(g.reconciliation_status)))
      throw new Error("اطلاعات مالی ضمانت ناقص یا ناسازگار است.");
  }
  for (const rawPension of pensions) {
    const p = record(rawPension);
    if (!uuid(p.id) || !nonEmpty(p.period_reference) || !decimal(p.amount) || !currency(p.currency) ||
      !nonEmpty(p.lifecycle_status) || !nullableTime(p.approved_at))
      throw new Error("اطلاعات حمایت دوره‌ای ناقص یا نامعتبر است.");
  }
  for (const rawCase of cases) {
    const c = record(rawCase);
    if (!uuid(c.id) || !aware(c.exit_at) || !aware(c.support_start_at) ||
      !Number.isInteger(c.duration_months) || (c.duration_months as number) < 1 || !nonEmpty(c.lifecycle_status))
      throw new Error("اطلاعات حمایت پس از خروج نامعتبر است.");
    for (const rawEntitlement of arr(c.entitlements, "استحقاق‌های پس از خروج")) {
      const e = record(rawEntitlement);
      if (!uuid(e.id) || !Number.isInteger(e.period_sequence) || (e.period_sequence as number) < 1 ||
        !nonEmpty(e.period_reference) || !aware(e.period_at) || !decimal(e.amount) || !currency(e.currency) ||
        !nonEmpty(e.lifecycle_status) || !nullableTime(e.approved_at))
        throw new Error("استحقاق دوره‌ای پس از خروج نامعتبر است.");
    }
  }
  for (const rawReturn of returns) {
    const item = record(rawReturn);
    if (!currency(item.currency) || !decimal(item.amount)) throw new Error("اطلاعات بازده برنامه نامعتبر است.");
  }
  return r as unknown as InstitutionFinancialCase;
}
export function verifiedBeneficiariesPage<T>(raw: unknown, programId: string): { items: T[]; limit: number; offset: number } {
  const r = record(raw);
  if (!matches(r.program_id, programId) || !page(r)) throw new Error("فهرست افراد یا صفحه‌بندی معتبر نیست.");
  const items = arr(r.items, "افراد");
  for (const rawPerson of items) {
    const p = record(rawPerson);
    if (!uuid(p.participant_id) || !uuid(p.episode_id) || !nonEmpty(p.participation_status) ||
      !nonEmpty(p.consent_state) || !aware(p.started_at) || !nullableTime(p.ended_at))
      throw new Error("اطلاعات فرد در برنامه معتبر نیست.");
  }
  return r as { items: T[]; limit: number; offset: number };
}
export function verifiedLenderGuaranteesPage<T>(raw: unknown, providerId: string): { items: T[]; limit: number; offset: number } {
  const r = record(raw);
  if (!matches(r.provider_id, providerId) || !page(r)) throw new Error("فهرست ضمانت یا صفحه‌بندی معتبر نیست.");
  for (const rawItem of arr(r.items, "ضمانت‌ها")) {
    const g = record(rawItem);
    if (!uuid(g.guarantee_case_id) || !nonEmpty(g.case_state) || !decimal(g.requested_principal) ||
      !nullableDecimal(g.reserved_guarantee_amount) || !nullableDecimal(g.issued_guarantee_amount) ||
      !decimal(g.current_guarantee_exposure) || !nonEmpty(g.guarantee_mode) || !currency(g.currency) ||
      !(g.loan_state === null || nonEmpty(g.loan_state)) || !nullableDecimal(g.original_principal) ||
      !checkMoney(g.outstanding_principal, g.loan_currency) || !nullableTime(g.reservation_expires_at) ||
      !nullableTime(g.disbursed_at) || !nullableTime(g.settled_at) || !nullableTime(g.last_synced_at))
      throw new Error("اطلاعات ضمانت متعلق به تأمین‌کننده معتبر نیست.");
  }
  return r as { items: T[]; limit: number; offset: number };
}
export function verifiedIntakePage(raw: unknown, selected: ServiceCode, expectedOffset: number, expectedLimit = 25): IntakePage {
  const r = record(raw);
  if (r.service_code !== selected || !page(r) || r.offset !== expectedOffset || r.limit !== expectedLimit || !aware(r.observed_at))
    throw new Error("پاسخ صف درخواست‌ها با خدمت یا صفحه انتخاب‌شده تطابق ندارد.");
  const items = arr(r.items, "درخواست‌ها");
  for (const rawItem of items) {
    const item = record(rawItem);
    if (item.service_code !== selected || item.status !== "RECEIVED" || !uuid(item.id) ||
      !uuid(item.participant_id) || !aware(item.submitted_at))
      throw new Error("پاسخ صف شامل درخواست یا وضعیت ناسازگار است.");
  }
  return r as unknown as IntakePage;
}
