import { api, type ServiceCode, type ServiceRequest } from "./api";

export type RequestFilter = "ALL" | ServiceCode;
export type ApplicantRequestPage = {
  items: ServiceRequest[];
  limit: number;
  offset: number;
  observed_at: string;
};
export const REQUEST_PAGE_LIMIT = 25;

const uuidPattern = /^[\da-f]{8}-[\da-f]{4}-[1-8][\da-f]{3}-[89ab][\da-f]{3}-[\da-f]{12}$/i;
const awareTimestamp = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/;

function isServiceCode(value: unknown): value is ServiceCode {
  return value === "LOAN_GUARANTEE" || value === "MONTHLY_PENSION" || value === "POST_EXIT_SUPPORT";
}

function validTimestamp(value: unknown): value is string {
  return typeof value === "string" && awareTimestamp.test(value) && Number.isFinite(Date.parse(value));
}

export function validateApplicantRequest(raw: unknown, expectedCode?: ServiceCode): ServiceRequest {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    throw new Error("داده درخواست معتبر نیست.");
  }
  const record = raw as Record<string, unknown>;
  if (
    typeof record.id !== "string" || !uuidPattern.test(record.id) ||
    !isServiceCode(record.service_code) ||
    (expectedCode !== undefined && record.service_code !== expectedCode) ||
    record.status !== "RECEIVED" ||
    !validTimestamp(record.submitted_at)
  ) {
    throw new Error("اطلاعات درخواست با قرارداد بک‌اند مطابقت ندارد.");
  }
  return {
    id: record.id,
    service_code: record.service_code,
    status: "RECEIVED",
    submitted_at: record.submitted_at,
  };
}

export function validateApplicantRequestPage(
  raw: unknown, filter: RequestFilter, offset: number,
): ApplicantRequestPage {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    throw new Error("صفحه درخواست‌ها معتبر نیست.");
  }
  const page = raw as Record<string, unknown>;
  if (
    page.limit !== REQUEST_PAGE_LIMIT || page.offset !== offset ||
    !validTimestamp(page.observed_at) ||
    !Array.isArray(page.items) || page.items.length > REQUEST_PAGE_LIMIT
  ) {
    throw new Error("محدوده یا زمان صفحه درخواست‌ها نامعتبر است.");
  }
  const items = page.items.map(item =>
    validateApplicantRequest(item, filter === "ALL" ? undefined : filter),
  );
  if (new Set(items.map(item => item.id.toLowerCase())).size !== items.length) {
    throw new Error("شناسه تکراری در فهرست درخواست‌ها دریافت شد.");
  }
  return {
    items, limit: REQUEST_PAGE_LIMIT, offset, observed_at: page.observed_at,
  };
}

export async function loadApplicantRequestPage(
  token: string, filter: RequestFilter, offset: number,
): Promise<ApplicantRequestPage> {
  if (
    !(filter === "ALL" || isServiceCode(filter)) ||
    !Number.isSafeInteger(offset) || offset < 0 || offset % REQUEST_PAGE_LIMIT !== 0
  ) {
    throw new Error("فیلتر یا صفحه درخواست‌ها نامعتبر است.");
  }
  const path = "/api/v1/applicant/service-requests?limit=" + REQUEST_PAGE_LIMIT +
    "&offset=" + offset +
    (filter === "ALL" ? "" : "&service_code=" + encodeURIComponent(filter));
  const response = await api<unknown>(path, token);
  return validateApplicantRequestPage(response, filter, offset);
}
