export type DirectoryKind = "identities" | "legal-entities" | "programs";
export type DirectoryPage<T> = {
  observed_at: string;
  items: T[];
  limit: number;
  offset: number;
};
export type HumanIdentity = {
  identity_id: string;
  identity_type: "STAFF" | "GOVERNANCE" | "AUDITOR";
  status: string;
  created_at: string;
};
export type LegalEntityReference = {
  legal_entity_id: string;
  legal_name: string;
  entity_type: string;
  status: string;
  version: number;
  created_at: string;
};
export type ProgramReference = {
  program_id: string;
  code: string;
  name: string;
  status: "ACTIVE" | "INACTIVE";
  legal_entity_id: string | null;
  version: number;
  created_at: string;
};

const uuidPattern = /^[a-f\d]{8}-[a-f\d]{4}-[1-8][a-f\d]{3}-[89ab][a-f\d]{3}-[a-f\d]{12}$/i;
const humanTypes = new Set(["STAFF", "GOVERNANCE", "AUDITOR"]);
const forbiddenFields = new Set([
  "external_subject", "national_id", "registration_identifier", "phone", "email",
  "contact_details", "created_by",
]);

function object(value: unknown): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("ساختار پاسخ دایرکتوری معتبر نیست.");
  }
  return value as Record<string, unknown>;
}
function rows(value: unknown): unknown[] {
  if (!Array.isArray(value)) throw new Error("فهرست دایرکتوری معتبر نیست.");
  return value;
}
function nonEmpty(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}
function uuid(value: unknown): value is string {
  return typeof value === "string" && uuidPattern.test(value);
}
function aware(value: unknown): value is string {
  return typeof value === "string" &&
    /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)$/.test(value) &&
    !Number.isNaN(Date.parse(value));
}
function privacySafe(item: Record<string, unknown>): void {
  for (const key of forbiddenFields) {
    if (Object.prototype.hasOwnProperty.call(item, key)) {
      throw new Error("پاسخ دایرکتوری شامل فیلد خارج از قرارداد حریم خصوصی است.");
    }
  }
}
function page(raw: unknown, limit: number, offset: number): {
  record: Record<string, unknown>;
  items: unknown[];
} {
  const record = object(raw);
  const items = rows(record.items);
  if (
    !aware(record.observed_at) ||
    record.limit !== limit ||
    record.offset !== offset ||
    !Number.isInteger(record.limit) ||
    !Number.isInteger(record.offset) ||
    items.length > limit
  ) {
    throw new Error("پاسخ دایرکتوری با صفحه درخواست‌شده تطابق ندارد.");
  }
  return { record, items };
}
export function adminDirectoryPath(
  kind: DirectoryKind,
  limit = 25,
  offset = 0,
): string {
  if (!Number.isSafeInteger(limit) || limit < 1 || limit > 100 ||
      !Number.isSafeInteger(offset) || offset < 0) {
    throw new Error("محدوده صفحه دایرکتوری معتبر نیست.");
  }
  const path = kind === "identities"
    ? "/api/v1/admin/directory/identities"
    : kind === "legal-entities"
      ? "/api/v1/admin/directory/legal-entities"
      : kind === "programs"
        ? "/api/v1/admin/directory/programs"
        : null;
  if (path === null) throw new Error("نوع دایرکتوری معتبر نیست.");
  return path + "?limit=" + limit + "&offset=" + offset;
}
export function verifiedHumanIdentityPage(
  raw: unknown,
  limit: number,
  offset: number,
): DirectoryPage<HumanIdentity> {
  const { record, items } = page(raw, limit, offset);
  for (const rawItem of items) {
    const item = object(rawItem);
    privacySafe(item);
    if (
      !uuid(item.identity_id) ||
      !humanTypes.has(String(item.identity_type)) ||
      !nonEmpty(item.status) ||
      !aware(item.created_at)
    ) {
      throw new Error("رکورد هویت انسانی ناقص یا نامعتبر است.");
    }
  }
  return record as unknown as DirectoryPage<HumanIdentity>;
}
export function verifiedLegalEntityPage(
  raw: unknown,
  limit: number,
  offset: number,
): DirectoryPage<LegalEntityReference> {
  const { record, items } = page(raw, limit, offset);
  for (const rawItem of items) {
    const item = object(rawItem);
    privacySafe(item);
    if (
      !uuid(item.legal_entity_id) ||
      !nonEmpty(item.legal_name) ||
      !nonEmpty(item.entity_type) ||
      !nonEmpty(item.status) ||
      !Number.isInteger(item.version) ||
      (item.version as number) < 1 ||
      !aware(item.created_at)
    ) {
      throw new Error("رکورد سازمانی ناقص یا نامعتبر است.");
    }
  }
  return record as unknown as DirectoryPage<LegalEntityReference>;
}
export function verifiedProgramPage(
  raw: unknown,
  limit: number,
  offset: number,
): DirectoryPage<ProgramReference> {
  const { record, items } = page(raw, limit, offset);
  for (const rawItem of items) {
    const item = object(rawItem);
    privacySafe(item);
    if (
      !uuid(item.program_id) ||
      !nonEmpty(item.code) ||
      !nonEmpty(item.name) ||
      !["ACTIVE", "INACTIVE"].includes(String(item.status)) ||
      !(item.legal_entity_id === null || uuid(item.legal_entity_id)) ||
      !Number.isInteger(item.version) ||
      (item.version as number) < 1 ||
      !aware(item.created_at)
    ) {
      throw new Error("رکورد برنامه ناقص یا نامعتبر است.");
    }
  }
  return record as unknown as DirectoryPage<ProgramReference>;
}
