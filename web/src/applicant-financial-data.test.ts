import { afterEach, describe, expect, it, vi } from "vitest";
import {
  loadApplicantFinancialCase, normalizeFinancialDecimal, validateApplicantFinancialCase,
} from "./applicant-financial-data";

const participant = "123e4567-e89b-42d3-a456-426614174000";
const guaranteeId = "123e4567-e89b-42d3-a456-426614174001";
const monthlyId = "123e4567-e89b-42d3-a456-426614174002";
const supportId = "123e4567-e89b-42d3-a456-426614174003";
const entitlementId = "123e4567-e89b-42d3-a456-426614174004";
const guarantee = {
  id: guaranteeId, status: "ACTIVE", requested_principal: "100000000.00",
  guarantee_exposure: "100000000.00", lender_record_status: "RECORDED",
  loan_state: "ACTIVE", outstanding_principal: "50000000.00", currency: "IRR",
};
const entitlement = {
  id: monthlyId, period_reference: "1405-08", amount: "1200000.00",
  currency: "IRR", status: "APPROVED", payment_status: "NOT_CONFIGURED",
};
const supportEntitlement = {
  id: entitlementId, period_reference: "1405-08", amount: "250000.00",
  currency: "IRR", status: "DRAFT", payment_status: "NOT_CONFIGURED",
};
const postExit = {
  id: supportId, status: "ACTIVE", exit_at: "2026-10-01T10:00:00+03:30",
  support_start_at: "2026-11-01T00:00:00+03:30", duration_months: 12,
  entitlements: [supportEntitlement],
};
const balance = {
  currency: "IRR", outstanding_principal: "50000000.00",
  guarantee_exposure: "100000000.00",
  realized_return_allocated_to_support: "450000.00",
  allocated_support: "300000.00", paid_amount: null,
  payment_status: "NOT_CONFIGURED",
};
const response = () => ({
  participant_id: participant,
  guarantee_cases: [guarantee],
  monthly_entitlements: [entitlement],
  post_exit_cases: [postExit],
  balances: [balance],
  external_price_source_status: "NOT_CONFIGURED",
  external_payment_status: "NOT_CONFIGURED",
});

afterEach(() => vi.unstubAllGlobals());

describe("applicant financial read model", () => {
  it("normalizes Decimal exponent notation without JS floating point", () => {
    expect(normalizeFinancialDecimal("0E-18", "zero")).toBe("0");
    expect(normalizeFinancialDecimal("1.25E+3", "scaled")).toBe("1250");
    expect(normalizeFinancialDecimal("1E-18", "fraction")).toBe("0.000000000000000001");
    expect(normalizeFinancialDecimal("-4.5000", "negative")).toBe("-4.5");
    expect(() => normalizeFinancialDecimal(0.1, "number")).toThrow();
    expect(() => normalizeFinancialDecimal("NaN", "nan")).toThrow();
    expect(() => normalizeFinancialDecimal("1E-19", "scale")).toThrow();
    expect(() => normalizeFinancialDecimal("1E+21", "precision")).toThrow();
  });

  it("validates and allowlists the full self-scoped financial response", () => {
    const result = validateApplicantFinancialCase({
      ...response(), national_id: "must-not-render", external_subject: "private",
      bank_account: "must-not-render",
    });
    expect(result.guarantee_cases[0]).toEqual(guarantee);
    expect(result.monthly_entitlements[0]).toEqual(entitlement);
    expect(result.post_exit_cases[0]).toMatchObject({
      id: supportId, duration_months: 12, entitlements: [supportEntitlement],
    });
    expect(result.balances[0]).toEqual(balance);
    expect(JSON.stringify(result)).not.toContain("national_id");
    expect(JSON.stringify(result)).not.toContain("private");
    expect(JSON.stringify(result)).not.toContain("bank_account");
  });

  it("preserves currency buckets and never synthesizes a missing amount as zero", () => {
    const data = response();
    data.balances = [
      balance,
      { ...balance, currency: "USD", outstanding_principal: null, guarantee_exposure: null,
        realized_return_allocated_to_support: null, allocated_support: null },
    ];
    const result = validateApplicantFinancialCase(data);
    expect(result.balances.map(item => item.currency)).toEqual(["IRR", "USD"]);
    expect(result.balances[1].outstanding_principal).toBeNull();
    expect(result.balances[1].guarantee_exposure).toBeNull();
  });

  it("rejects duplicate currency buckets and duplicate record identities", () => {
    expect(() => validateApplicantFinancialCase({
      ...response(), balances: [balance, { ...balance, allocated_support: "1" }],
    })).toThrow();
    expect(() => validateApplicantFinancialCase({
      ...response(), guarantee_cases: [guarantee, guarantee],
    })).toThrow();
    expect(() => validateApplicantFinancialCase({
      ...response(), post_exit_cases: [{ ...postExit, entitlements: [supportEntitlement, supportEntitlement] }],
    })).toThrow();
  });

  it("rejects unrecognized lifecycle states, malformed IDs, and unzoned timestamps", () => {
    expect(() => validateApplicantFinancialCase({
      ...response(), guarantee_cases: [{ ...guarantee, status: "APPROVED" }],
    })).toThrow();
    expect(() => validateApplicantFinancialCase({
      ...response(), monthly_entitlements: [{ ...entitlement, status: "PAID" }],
    })).toThrow();
    expect(() => validateApplicantFinancialCase({
      ...response(), post_exit_cases: [{ ...postExit, status: "PAID" }],
    })).toThrow();
    expect(() => validateApplicantFinancialCase({
      ...response(), participant_id: "BD-1024",
    })).toThrow();
    expect(() => validateApplicantFinancialCase({
      ...response(), post_exit_cases: [{ ...postExit, exit_at: "2026-10-01T10:00:00" }],
    })).toThrow();
  });

  it("rejects invented payment values or incorrectly claimed lender mirror states", () => {
    expect(() => validateApplicantFinancialCase({
      ...response(), balances: [{ ...balance, paid_amount: "0" }],
    })).toThrow();
    expect(() => validateApplicantFinancialCase({
      ...response(), external_payment_status: "CONNECTED",
    })).toThrow();
    expect(() => validateApplicantFinancialCase({
      ...response(), monthly_entitlements: [{ ...entitlement, payment_status: "PAID" }],
    })).toThrow();
    expect(() => validateApplicantFinancialCase({
      ...response(), guarantee_cases: [{
        ...guarantee, lender_record_status: "NOT_RECORDED",
      }],
    })).toThrow();
    expect(() => validateApplicantFinancialCase({
      ...response(), guarantee_cases: [{
        ...guarantee, lender_record_status: "RECORDED", loan_state: "UNKNOWN",
      }],
    })).toThrow();
  });

  it("rejects amounts and lists outside the persisted numeric and API bounds", () => {
    expect(() => validateApplicantFinancialCase({
      ...response(), guarantee_cases: [{ ...guarantee, requested_principal: "-1" }],
    })).toThrow();
    expect(() => validateApplicantFinancialCase({
      ...response(), balances: Array(101).fill(balance).map((item, i) => ({ ...item, currency: "C" + i })),
    })).toThrow();
    expect(() => validateApplicantFinancialCase({
      ...response(), post_exit_cases: [{ ...postExit, duration_months: 37 }],
    })).toThrow();
  });

  it("calls only the authenticated participant financial GET", async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => response() });
    vi.stubGlobal("fetch", fetch);
    const result = await loadApplicantFinancialCase("memory-token");
    expect(result.participant_id).toBe(participant);
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch.mock.calls[0][0]).toBe("/api/v1/applicant/financial-case");
    expect(fetch.mock.calls[0][1]).toMatchObject({
      credentials: "omit", cache: "no-store", headers: { Authorization: "Bearer memory-token" },
    });
  });

  it("fails closed on missing authentication and denied API reads", async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: false, status: 403 });
    vi.stubGlobal("fetch", fetch);
    await expect(loadApplicantFinancialCase("token")).rejects.toMatchObject({ status: 403 });
    await expect(loadApplicantFinancialCase("")).rejects.toMatchObject({ status: 401 });
    expect(fetch).toHaveBeenCalledTimes(1);
  });
});
