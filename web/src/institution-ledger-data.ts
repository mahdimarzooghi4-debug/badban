import { type Page } from "./api";
import { checkedReadPage } from "./paged-read-data";
import { requireUuid } from "./operational-data";

export const LEDGER_PAGE_SIZE = 25;
const uuidPattern = /^[a-f\d]{8}-[a-f\d]{4}-[1-8][a-f\d]{3}-[89ab][a-f\d]{3}-[a-f\d]{12}$/i;
const accountClasses = new Set([
  "CONTROLLED_ASSET",
  "OWNER_OR_ENTITLEMENT_BALANCE",
  "RETURN_OR_INCOME_CLEARING",
  "LOSS_OR_COST_CONTROL",
  "MEMORANDUM_CONTROL",
]);
const ledgerLayers = new Set(["MONETARY", "MEMORANDUM_CONTROL", "EXTERNAL_MIRROR"]);
const normalBalances = new Set(["DEBIT", "CREDIT", "MEMO"]);
const privateDimensions = [
  "participant_id",
  "economic_owner_id",
  "provider_id",
  "asset_position_id",
  "guarantee_case_id",
  "claim_id",
  "reserve_account_id",
] as const;
type RecordValue = Record<string, unknown>;

export interface FinancialHistoryPosting {
  account_code: string;
  account_name: string;
  account_class: string;
  economic_owner_type: string;
  normal_balance: "DEBIT" | "CREDIT" | "MEMO";
  ledger_layer: "MONETARY" | "MEMORANDUM_CONTROL" | "EXTERNAL_MIRROR";
  debit_amount: string;
  credit_amount: string;
  currency: string;
}
export interface FinancialHistoryEntry {
  id: string;
  state: "POSTED";
  business_event_type: string;
  currency: string;
  effective_at: string;
  posted_at: string;
  reversal_of_entry_id: string | null;
  policy_version_reference: string | null;
  posting_template_reference: string | null;
  evidence_reference: string;
  postings: FinancialHistoryPosting[];
}
export interface FinancialHistoryPage {
  source_type: "INTERNAL_BADBAN_POSTED_JOURNAL";
  program_id: string;
  legal_entity_id: string;
  snapshot_at: string;
  items: FinancialHistoryEntry[];
  limit: number;
  offset: number;
  total_entries: number;
}
export interface ProgramStatementRow {
  account_code: string;
  account_name: string;
  account_class: string;
  currency: string;
  legal_entity_id: string;
  economic_owner_type: string;
  ledger_layer: "MONETARY" | "MEMORANDUM_CONTROL" | "EXTERNAL_MIRROR";
  normal_balance: "DEBIT" | "CREDIT" | "MEMO";
  balance: string;
}
export interface ProgramStatement {
  source_type: "INTERNAL_BADBAN_POSTED_JOURNAL";
  program_id: string;
  legal_entity_id: string;
  snapshot_at: string;
  received_at: string;
  source_reference: string;
  schema_version: string;
  contract_version: string;
  mapping_version: string;
  content_hash: string;
  evidence_references: string[];
  items: ProgramStatementRow[];
  limit: number;
  offset: number;
  total_rows: number;
}

function record(value: unknown): RecordValue {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("ساختار پاسخ دفترکل معتبر نیست.");
  }
  return value as RecordValue;
}
function nonEmpty(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}
function uuid(value: unknown): value is string {
  return typeof value === "string" && uuidPattern.test(value);
}
function decimal(value: unknown): value is string {
  return typeof value === "string" && /^-?(?:0|[1-9]\d*)(?:\.\d+)?$/.test(value);
}
function nonNegativeDecimal(value: unknown): value is string {
  return typeof value === "string" && /^(?:0|[1-9]\d*)(?:\.\d+)?$/.test(value);
}
function currency(value: unknown): value is string {
  return typeof value === "string" && /^[A-Z]{3,8}$/.test(value);
}
function aware(value: unknown): value is string {
  return typeof value === "string" &&
    /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)$/.test(value) &&
    !Number.isNaN(Date.parse(value));
}
function nullableText(value: unknown): value is string | null {
  return value === null || nonEmpty(value);
}
function nullableUuid(value: unknown): value is string | null {
  return value === null || uuid(value);
}
function hasPrivateDimension(value: RecordValue): boolean {
  return privateDimensions.some(key => Object.prototype.hasOwnProperty.call(value, key));
}
function exactPage(raw: unknown, limit: number, offset: number): RecordValue & {
  items: unknown[];
  limit: number;
  offset: number;
} {
  checkedReadPage(limit, offset);
  const page = record(raw);
  if (page.limit !== limit || page.offset !== offset || !Array.isArray(page.items) ||
      page.items.length > limit) {
    throw new Error("صفحه دفترکل با محدوده درخواست‌شده هم‌خوانی ندارد.");
  }
  return page as RecordValue & { items: unknown[]; limit: number; offset: number };
}

export function financialHistoryPath(
  programId: string,
  limit = LEDGER_PAGE_SIZE,
  offset = 0,
  snapshotAt?: string,
): string {
  checkedReadPage(limit, offset);
  const path = "/api/v1/support-institution/programs/" + requireUuid(programId) +
    "/financial-history?limit=" + limit + "&offset=" + offset;
  return snapshotAt ? path + "&snapshot_at=" + encodeURIComponent(snapshotAt) : path;
}
export function financialStatementPath(
  programId: string,
  limit = LEDGER_PAGE_SIZE,
  offset = 0,
  snapshotAt?: string,
): string {
  checkedReadPage(limit, offset);
  const path = "/api/v1/support-institution/programs/" + requireUuid(programId) +
    "/financial-statement?limit=" + limit + "&offset=" + offset;
  return snapshotAt ? path + "&snapshot_at=" + encodeURIComponent(snapshotAt) : path;
}

export function verifiedFinancialHistoryPage(
  raw: unknown,
  programId: string,
  limit: number,
  offset: number,
  expectedSnapshotAt?: string,
): FinancialHistoryPage {
  const page = exactPage(raw, limit, offset);
  if (page.source_type !== "INTERNAL_BADBAN_POSTED_JOURNAL" ||
      !uuid(page.legal_entity_id) || !aware(page.snapshot_at) ||
      (expectedSnapshotAt !== undefined && page.snapshot_at !== expectedSnapshotAt) ||
      typeof page.total_entries !== "number" || !Number.isSafeInteger(page.total_entries) ||
      page.total_entries < page.items.length ||
      typeof page.program_id !== "string" ||
      page.program_id.toLowerCase() !== requireUuid(programId)) {
    throw new Error("محدوده یا منبع سوابق دفترکل معتبر نیست.");
  }
  const ids = new Set<string>();
  for (const rawEntry of page.items) {
    const entry = record(rawEntry);
    if (!uuid(entry.id) || ids.has(entry.id.toLowerCase()) || entry.state !== "POSTED" ||
        !nonEmpty(entry.business_event_type) || !currency(entry.currency) ||
        !aware(entry.effective_at) || !aware(entry.posted_at) ||
        !nullableUuid(entry.reversal_of_entry_id) ||
        !nullableText(entry.policy_version_reference) ||
        !nullableText(entry.posting_template_reference) ||
        typeof entry.evidence_reference !== "string" ||
        entry.evidence_reference.toLowerCase() !== "journal-entry:" + entry.id.toLowerCase() ||
        !Array.isArray(entry.postings) ||
        entry.postings.length < 2) {
      throw new Error("ثبت دفترکل ناقص یا نامعتبر است.");
    }
    ids.add(entry.id.toLowerCase());
    for (const rawPosting of entry.postings) {
      const posting = record(rawPosting);
      if (hasPrivateDimension(posting) || !nonEmpty(posting.account_code) ||
          !nonEmpty(posting.account_name) ||
          typeof posting.account_class !== "string" || !accountClasses.has(posting.account_class) ||
          !nonEmpty(posting.economic_owner_type) ||
          typeof posting.normal_balance !== "string" || !normalBalances.has(posting.normal_balance) ||
          typeof posting.ledger_layer !== "string" || !ledgerLayers.has(posting.ledger_layer) ||
          !nonNegativeDecimal(posting.debit_amount) ||
          !nonNegativeDecimal(posting.credit_amount) || posting.currency !== entry.currency) {
        throw new Error("ردیف دفترکل شامل ابعاد خصوصی یا مقدار ناسازگار است.");
      }
    }
  }
  return page as unknown as FinancialHistoryPage;
}

export function verifiedProgramStatement(
  raw: unknown,
  programId: string,
  limit: number,
  offset: number,
  expectedSnapshotAt?: string,
): ProgramStatement {
  const page = exactPage(raw, limit, offset);
  if (page.source_type !== "INTERNAL_BADBAN_POSTED_JOURNAL" ||
      typeof page.program_id !== "string" ||
      page.program_id.toLowerCase() !== requireUuid(programId) ||
      !uuid(page.legal_entity_id) ||
      !aware(page.snapshot_at) ||
      (expectedSnapshotAt !== undefined && page.snapshot_at !== expectedSnapshotAt) ||
      !aware(page.received_at) ||
      !nonEmpty(page.source_reference) || !nonEmpty(page.schema_version) ||
      !nonEmpty(page.contract_version) || !nonEmpty(page.mapping_version) ||
      typeof page.content_hash !== "string" || !/^[a-f\d]{64}$/.test(page.content_hash) ||
      typeof page.total_rows !== "number" || !Number.isSafeInteger(page.total_rows) ||
      page.total_rows < page.items.length || !Array.isArray(page.evidence_references) ||
      page.evidence_references.length < 1 || page.evidence_references.length > 1000) {
    throw new Error("فراداده صورت‌وضعیت دفترکل معتبر نیست.");
  }
  const evidence = new Set<string>();
  for (const reference of page.evidence_references) {
    if (typeof reference !== "string" || !/^journal-entry:[a-f\d-]{36}$/i.test(reference) ||
        evidence.has(reference)) {
      throw new Error("ردپای شواهد دفترکل معتبر نیست.");
    }
    evidence.add(reference);
  }
  const rowKeys = new Set<string>();
  for (const rawRow of page.items) {
    const row = record(rawRow);
    if (hasPrivateDimension(row) || !nonEmpty(row.account_code) || !nonEmpty(row.account_name) ||
        typeof row.account_class !== "string" || !accountClasses.has(row.account_class) ||
        !currency(row.currency) || row.legal_entity_id !== page.legal_entity_id ||
        !nonEmpty(row.economic_owner_type) ||
        typeof row.ledger_layer !== "string" || !ledgerLayers.has(row.ledger_layer) ||
        typeof row.normal_balance !== "string" || !normalBalances.has(row.normal_balance) ||
        !decimal(row.balance)) {
      throw new Error("ردیف صورت‌وضعیت دارای شناسه خصوصی یا ابعاد مالی ناسازگار است.");
    }
    const key = [
      row.account_code, row.currency, row.legal_entity_id, row.economic_owner_type,
      row.ledger_layer, row.normal_balance,
    ].join("|");
    if (rowKeys.has(key)) throw new Error("ردیف تجمیعی تکراری در صورت‌وضعیت وجود دارد.");
    rowKeys.add(key);
  }
  return page as unknown as ProgramStatement;
}

export type LedgerProgramPage = Page<{
  program_id: string;
  code: string;
  name: string;
  status: string;
}>;
