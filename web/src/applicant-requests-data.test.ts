import { afterEach, describe, expect, it, vi } from "vitest";
import {
  REQUEST_PAGE_LIMIT, loadApplicantRequestPage, validateApplicantRequest,
  validateApplicantRequestPage,
} from "./applicant-requests-data";

const id = "123e4567-e89b-42d3-a456-426614174000";
const id2 = "123e4567-e89b-42d3-a456-426614174001";
const submitted_at = "2026-11-05T12:30:00+00:00";
const record = { id, service_code: "LOAN_GUARANTEE", status: "RECEIVED", submitted_at };
const page = (items: unknown[], offset = 0) => ({
  items, limit: REQUEST_PAGE_LIMIT, offset, observed_at: submitted_at,
});

afterEach(() => vi.unstubAllGlobals());

describe("Figma applicant requests read model", () => {
  it("uses only the authenticated self-scoped endpoint and exact server filter", async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => page([record], 25) });
    vi.stubGlobal("fetch", fetch);
    const result = await loadApplicantRequestPage("memory-token", "LOAN_GUARANTEE", 25);
    expect(result.items).toEqual([record]);
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch.mock.calls[0][0]).toBe(
      "/api/v1/applicant/service-requests?limit=25&offset=25&service_code=LOAN_GUARANTEE",
    );
    expect(fetch.mock.calls[0][1]).toMatchObject({
      credentials: "omit", cache: "no-store", headers: { Authorization: "Bearer memory-token" },
    });
  });

  it("uses the unfiltered endpoint without participant IDs or invented counts", async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => page([]) });
    vi.stubGlobal("fetch", fetch);
    const result = await loadApplicantRequestPage("token", "ALL", 0);
    expect(result.items).toEqual([]);
    expect(fetch.mock.calls[0][0]).toBe("/api/v1/applicant/service-requests?limit=25&offset=0");
    expect(Object.keys(result).sort()).toEqual(["items", "limit", "observed_at", "offset"]);
  });

  it("rejects unexpected filter/offset before network I/O", async () => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    await expect(loadApplicantRequestPage("token", "ALL", -1)).rejects.toThrow("نامعتبر");
    await expect(loadApplicantRequestPage("token", "ALL", 3)).rejects.toThrow("نامعتبر");
    await expect(loadApplicantRequestPage("token", "ALL", Number.MAX_SAFE_INTEGER + 1)).rejects.toThrow("نامعتبر");
    expect(fetch).not.toHaveBeenCalled();
  });

  it("fails closed if server returns another page or service, duplicate IDs or more than 25 rows", () => {
    expect(() => validateApplicantRequestPage(page([record], 25), "ALL", 0)).toThrow();
    expect(() => validateApplicantRequestPage(page([record]), "MONTHLY_PENSION", 0)).toThrow();
    expect(() => validateApplicantRequestPage(page([record, record]), "ALL", 0)).toThrow();
    expect(() => validateApplicantRequestPage(page(Array(26).fill(record)), "ALL", 0)).toThrow();
    expect(() => validateApplicantRequestPage({ ...page([]), limit: 50 }, "ALL", 0)).toThrow();
    expect(() => validateApplicantRequestPage({ ...page([]), observed_at: "2026-11-05" }, "ALL", 0)).toThrow();
  });

  it("requires an actual RECEIVED record, valid UUID, and timezone-aware timestamp", () => {
    expect(() => validateApplicantRequest({ ...record, status: "APPROVED" })).toThrow();
    expect(() => validateApplicantRequest({ ...record, id: "BD-RQ-1024" })).toThrow();
    expect(() => validateApplicantRequest({ ...record, submitted_at: "2026-11-05T12:30:00" })).toThrow();
    expect(() => validateApplicantRequest({ ...record, service_code: "FAKE" })).toThrow();
    expect(() => validateApplicantRequest(record, "POST_EXIT_SUPPORT")).toThrow();
    expect(validateApplicantRequest({ ...record, id: id2, personal_name: "should not render" }))
      .toEqual({ ...record, id: id2 });
  });

  it("propagates forbidden reads without stale/synthetic fallback data", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 403 }));
    await expect(loadApplicantRequestPage("token", "ALL", 0)).rejects.toMatchObject({ status: 403 });
  });
});
