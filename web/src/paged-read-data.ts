import { type Beneficiary, type Guarantee, type Page, type Program, type Provider } from "./api";
import { requireUuid, verifiedBeneficiariesPage, verifiedLenderGuaranteesPage } from "./operational-data";

export const READ_PAGE_SIZE = 25;
export type ReadKind = "programs" | "beneficiaries" | "providers" | "guarantees";
type RecordValue = Record<string, unknown>;
const uuidPattern = /^[a-f\d]{8}-[a-f\d]{4}-[1-8][a-f\d]{3}-[89ab][a-f\d]{3}-[a-f\d]{12}$/i;

function record(value: unknown): RecordValue {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("پاسخ فهرست معتبر نیست.");
  return value as RecordValue;
}
function nonEmpty(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}
export function checkedReadPage(limit: number, offset: number): void {
  if (!Number.isSafeInteger(limit) || limit < 1 || limit > 100 ||
      !Number.isSafeInteger(offset) || offset < 0 || offset > Number.MAX_SAFE_INTEGER - limit) {
    throw new Error("شماره صفحه یا تعداد رکورد معتبر نیست.");
  }
}
export function readPagePath(kind: ReadKind, limit = READ_PAGE_SIZE, offset = 0, id?: string): string {
  checkedReadPage(limit, offset);
  let endpoint: string;
  if (kind === "programs") {
    if (id !== undefined) throw new Error("شناسه اضافه برای فهرست برنامه‌ها مجاز نیست.");
    endpoint = "/api/v1/support-institution/programs";
  } else if (kind === "providers") {
    if (id !== undefined) throw new Error("شناسه اضافه برای فهرست تأمین‌کنندگان مجاز نیست.");
    endpoint = "/api/v1/lender/providers";
  } else if (kind === "beneficiaries") {
    if (!id) throw new Error("شناسه برنامه ضروری است.");
    endpoint = "/api/v1/support-institution/programs/" + requireUuid(id) + "/beneficiaries";
  } else if (kind === "guarantees") {
    if (!id) throw new Error("شناسه تأمین‌کننده ضروری است.");
    endpoint = "/api/v1/lender/providers/" + requireUuid(id) + "/guarantees";
  } else {
    throw new Error("نوع فهرست معتبر نیست.");
  }
  return endpoint + "?limit=" + limit + "&offset=" + offset;
}

function exactPage(raw: unknown, limit: number, offset: number): RecordValue & { items: unknown[]; limit: number; offset: number } {
  checkedReadPage(limit, offset);
  const r = record(raw);
  if (r.limit !== limit || r.offset !== offset || !Array.isArray(r.items) || r.items.length > limit) {
    throw new Error("پاسخ فهرست با صفحه درخواست‌شده هم‌خوانی ندارد.");
  }
  return r as RecordValue & { items: unknown[]; limit: number; offset: number };
}
function uniqueIDs(items: unknown[], field: string): void {
  const found = new Set<string>();
  for (const item of items) {
    const r = record(item);
    const id = r[field];
    if (typeof id !== "string" || !uuidPattern.test(id) || found.has(id.toLowerCase())) {
      throw new Error("شناسه رکورد تکراری یا نامعتبر است.");
    }
    found.add(id.toLowerCase());
  }
}
export function verifiedProgramsPage(raw: unknown, limit: number, offset: number): Page<Program> {
  const r = exactPage(raw, limit, offset);
  uniqueIDs(r.items, "program_id");
  for (const item of r.items) {
    const row = record(item);
    if (!nonEmpty(row.code) || !nonEmpty(row.name) || row.status !== "ACTIVE") {
      throw new Error("برنامه مجاز در پاسخ معتبر نیست.");
    }
  }
  return r as unknown as Page<Program>;
}
export function verifiedProvidersPage(raw: unknown, limit: number, offset: number): Page<Provider> {
  const r = exactPage(raw, limit, offset);
  uniqueIDs(r.items, "provider_id");
  for (const item of r.items) {
    const row = record(item);
    if (!nonEmpty(row.provider_code) || !nonEmpty(row.display_name)) {
      throw new Error("تأمین‌کننده در پاسخ معتبر نیست.");
    }
  }
  return r as unknown as Page<Provider>;
}
export function verifiedPagedBeneficiaries(raw: unknown, programId: string, limit: number, offset: number): Page<Beneficiary> {
  exactPage(raw, limit, offset);
  const r = verifiedBeneficiariesPage<Beneficiary>(raw, requireUuid(programId));
  uniqueIDs(r.items, "episode_id");
  return r;
}
export function verifiedPagedGuarantees(raw: unknown, providerId: string, limit: number, offset: number): Page<Guarantee> {
  exactPage(raw, limit, offset);
  const r = verifiedLenderGuaranteesPage<Guarantee>(raw, requireUuid(providerId));
  uniqueIDs(r.items, "guarantee_case_id");
  return r;
}
export function nextPageOffset(offset: number, pageLength: number, limit = READ_PAGE_SIZE): number | null {
  checkedReadPage(limit, offset);
  if (!Number.isSafeInteger(pageLength) || pageLength < 0 || pageLength > limit) {
    throw new Error("تعداد ردیف‌های صفحه معتبر نیست.");
  }
  // The backend exposes no total count. A full page may or may not have a next page.
  return pageLength === limit ? offset + limit : null;
}
export function previousPageOffset(offset: number, limit = READ_PAGE_SIZE): number {
  checkedReadPage(limit, offset);
  return Math.max(0, offset - limit);
}
