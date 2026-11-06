import {
  api,
  type Balance,
  type EntitlementSummary,
  type FinancialCase,
  type GuaranteeCaseSummary,
  type PostExitCaseSummary,
} from "./api";

const uuidPattern = /^[\da-f]{8}-[\da-f]{4}-[1-8][\da-f]{3}-[89ab][\da-f]{3}-[\da-f]{12}$/i;
const timestampPattern = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/;
const guaranteeStates = new Set([
  "REQUESTED", "RESERVED", "ISSUED", "ACTIVE", "DELINQUENT",
  "CLAIM_PENDING", "CLAIM_APPROVED", "CLAIM_REJECTED", "ENFORCEMENT",
  "SETTLEMENT", "RELEASED", "CLOSED", "CANCELLED", "EXPIRED",
]);
const loanStates = new Set(["PENDING", "ACTIVE", "DELINQUENT", "SETTLED", "REPLACED"]);
const entitlementStates = new Set(["DRAFT", "APPROVED", "CANCELLED"]);
const postExitStates = new Set(["DRAFT", "ACTIVE", "SUSPENDED", "COMPLETED", "CANCELLED"]);
const PAYMENT_NOT_CONFIGURED = "NOT_CONFIGURED";

function object(value: unknown, field: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("ساختار " + field + " در پاسخ مالی معتبر نیست.");
  }
  return value as Record<string, unknown>;
}

function list(value: unknown, field: string): unknown[] {
  if (!Array.isArray(value) || value.length > 100) {
    throw new Error("فهرست " + field + " معتبر نیست یا از سقف ۱۰۰ مورد عبور کرده است.");
  }
  return value;
}

function text(value: unknown, field: string, max = 255): string {
  if (typeof value !== "string" || value.trim() !== value || value.length === 0 || value.length > max) {
    throw new Error("فیلد " + field + " در پاسخ مالی معتبر نیست.");
  }
  return value;
}

function uuid(value: unknown, field: string): string {
  const result = text(value, field, 36);
  if (!uuidPattern.test(result)) throw new Error("شناسه " + field + " معتبر نیست.");
  return result;
}

function currency(value: unknown): string {
  return text(value, "currency", 16);
}

/** Expand Decimal strings (including e.g. Decimal('0E-18')) without using JS Number. */
export function normalizeFinancialDecimal(value: unknown, field: string, nullable = false): string | null {
  if (value === null && nullable) return null;
  if (typeof value !== "string") throw new Error("مبلغ " + field + " باید رشته دقیق مالی باشد.");
  const match = /^(-?)(\d+)(?:\.(\d+))?(?:[eE]([+-]?\d+))?$/.exec(value);
  if (!match) throw new Error("مبلغ " + field + " معتبر نیست.");
  const sign = match[1];
  const integer = match[2];
  const fraction = match[3] ?? "";
  const exponent = Number(match[4] ?? "0");
  if (!Number.isSafeInteger(exponent) || Math.abs(exponent) > 38) {
    throw new Error("دقت مبلغ " + field + " خارج از محدوده است.");
  }
  const digits = integer + fraction;
  const point = integer.length + exponent;
  let whole: string;
  let decimal: string;
  if (point <= 0) {
    whole = "0";
    decimal = "0".repeat(-point) + digits;
  } else if (point >= digits.length) {
    whole = digits + "0".repeat(point - digits.length);
    decimal = "";
  } else {
    whole = digits.slice(0, point);
    decimal = digits.slice(point);
  }
  whole = whole.replace(/^0+(?=\d)/, "");
  decimal = decimal.replace(/0+$/, "");
  if (whole.length > 20 || decimal.length > 18) {
    throw new Error("دقت مبلغ " + field + " با قرارداد NUMERIC(38,18) سازگار نیست.");
  }
  const zero = /^0+$/.test(whole) && decimal.length === 0;
  return (sign && !zero ? "-" : "") + whole + (decimal ? "." + decimal : "");
}

function timestamp(value: unknown, field: string): string {
  const result = text(value, field, 64);
  if (!timestampPattern.test(result) || !Number.isFinite(Date.parse(result))) {
    throw new Error("زمان " + field + " باید همراه منطقه زمانی باشد.");
  }
  return result;
}

function state<T extends string>(value: unknown, allowed: Set<string>, field: string): T {
  const result = text(value, field, 40);
  if (!allowed.has(result)) throw new Error("وضعیت " + field + " در قرارداد مالی شناخته‌شده نیست.");
  return result as T;
}

function uniqueIds<T extends { id: string }>(items: T[], field: string): T[] {
  if (new Set(items.map(item => item.id.toLowerCase())).size !== items.length) {
    throw new Error("شناسه تکراری در " + field + " دریافت شد.");
  }
  return items;
}

function entitlement(raw: unknown, field: string): EntitlementSummary {
  const item = object(raw, field);
  if (item.payment_status !== PAYMENT_NOT_CONFIGURED) {
    throw new Error("وضعیت پرداخت " + field + " خارج از قرارداد فعلی است.");
  }
  const amount = normalizeFinancialDecimal(item.amount, field + ".amount");
  if (amount === null || amount.startsWith("-") || amount === "0") {
    throw new Error("مبلغ استحقاق " + field + " باید مثبت باشد.");
  }
  return {
    id: uuid(item.id, field + ".id"),
    period_reference: text(item.period_reference, field + ".period_reference", 120),
    amount,
    currency: currency(item.currency),
    status: state<EntitlementSummary["status"]>(item.status, entitlementStates, field + ".status"),
    payment_status: PAYMENT_NOT_CONFIGURED,
  };
}

function guarantee(raw: unknown, index: number): GuaranteeCaseSummary {
  const field = "guarantee_cases[" + index + "]";
  const item = object(raw, field);
  const lenderRecord = item.lender_record_status;
  if (lenderRecord !== "RECORDED" && lenderRecord !== "NOT_RECORDED") {
    throw new Error("وضعیت ثبت تأمین‌کننده معتبر نیست.");
  }
  const loanState = item.loan_state === null
    ? null
    : state<NonNullable<GuaranteeCaseSummary["loan_state"]>>(item.loan_state, loanStates, field + ".loan_state");
  const outstanding = normalizeFinancialDecimal(item.outstanding_principal, field + ".outstanding_principal", true);
  if (
    (lenderRecord === "RECORDED" && (loanState === null || outstanding === null)) ||
    (lenderRecord === "NOT_RECORDED" && (loanState !== null || outstanding !== null))
  ) {
    throw new Error("اطلاعات آینه تسهیلات با وضعیت ثبت تأمین‌کننده سازگار نیست.");
  }
  const requested = normalizeFinancialDecimal(item.requested_principal, field + ".requested_principal");
  const exposure = normalizeFinancialDecimal(item.guarantee_exposure, field + ".guarantee_exposure");
  if (requested === null || requested.startsWith("-") || requested === "0" ||
      exposure === null || exposure.startsWith("-")) {
    throw new Error("مبالغ ضمانت با قرارداد مالی سازگار نیستند.");
  }
  return {
    id: uuid(item.id, field + ".id"),
    status: state<GuaranteeCaseSummary["status"]>(item.status, guaranteeStates, field + ".status"),
    requested_principal: requested,
    guarantee_exposure: exposure,
    lender_record_status: lenderRecord,
    loan_state: loanState,
    outstanding_principal: outstanding,
    currency: currency(item.currency),
  };
}

function postExit(raw: unknown, index: number): PostExitCaseSummary {
  const field = "post_exit_cases[" + index + "]";
  const item = object(raw, field);
  const duration = item.duration_months;
  if (!Number.isInteger(duration) || (duration as number) < 1 || (duration as number) > 36) {
    throw new Error("مدت حمایت پس از خروج معتبر نیست.");
  }
  const entitlements = list(item.entitlements, field + ".entitlements")
    .map((row, i) => entitlement(row, field + ".entitlements[" + i + "]"));
  return {
    id: uuid(item.id, field + ".id"),
    status: state<PostExitCaseSummary["status"]>(item.status, postExitStates, field + ".status"),
    exit_at: timestamp(item.exit_at, field + ".exit_at"),
    support_start_at: timestamp(item.support_start_at, field + ".support_start_at"),
    duration_months: duration as number,
    entitlements: uniqueIds(entitlements, field + ".entitlements"),
  };
}

function balance(raw: unknown, index: number): Balance {
  const field = "balances[" + index + "]";
  const item = object(raw, field);
  if (item.payment_status !== PAYMENT_NOT_CONFIGURED || item.paid_amount !== null) {
    throw new Error("اطلاعات پرداخت نباید بدون اتصال تسویه نمایش داده شود.");
  }
  return {
    currency: currency(item.currency),
    outstanding_principal: normalizeFinancialDecimal(item.outstanding_principal, field + ".outstanding_principal", true),
    guarantee_exposure: normalizeFinancialDecimal(item.guarantee_exposure, field + ".guarantee_exposure", true),
    realized_return_allocated_to_support: normalizeFinancialDecimal(
      item.realized_return_allocated_to_support, field + ".realized_return_allocated_to_support", true,
    ),
    allocated_support: normalizeFinancialDecimal(item.allocated_support, field + ".allocated_support", true),
    paid_amount: null,
    payment_status: PAYMENT_NOT_CONFIGURED,
  };
}

export function validateApplicantFinancialCase(raw: unknown): FinancialCase {
  const data = object(raw, "financial_case");
  if (
    data.external_price_source_status !== PAYMENT_NOT_CONFIGURED ||
    data.external_payment_status !== PAYMENT_NOT_CONFIGURED
  ) {
    throw new Error("وضعیت اتصال منبع قیمت یا پرداخت خارج از قرارداد فعلی است.");
  }
  const guarantees = uniqueIds(
    list(data.guarantee_cases, "guarantee_cases").map(guarantee),
    "guarantee_cases",
  );
  const monthly = uniqueIds(
    list(data.monthly_entitlements, "monthly_entitlements")
      .map((item, index) => entitlement(item, "monthly_entitlements[" + index + "]")),
    "monthly_entitlements",
  );
  const postExit = uniqueIds(
    list(data.post_exit_cases, "post_exit_cases").map(postExit),
    "post_exit_cases",
  );
  const nestedEntitlements = postExit.reduce((total, item) => total + item.entitlements.length, 0);
  if (nestedEntitlements > 100) throw new Error("تعداد استحقاق‌های پس از خروج از سقف پاسخ API عبور کرده است.");
  const balances = list(data.balances, "balances").map(balance);
  if (new Set(balances.map(item => item.currency)).size !== balances.length) {
    throw new Error("برای یک ارز بیش از یک سبد مانده دریافت شد.");
  }
  return {
    participant_id: uuid(data.participant_id, "participant_id"),
    guarantee_cases: guarantees,
    monthly_entitlements: monthly,
    post_exit_cases: postExit,
    balances,
    external_price_source_status: PAYMENT_NOT_CONFIGURED,
    external_payment_status: PAYMENT_NOT_CONFIGURED,
  };
}

export async function loadApplicantFinancialCase(token: string): Promise<FinancialCase> {
  return validateApplicantFinancialCase(
    await api<unknown>("/api/v1/applicant/financial-case", token),
  );
}
