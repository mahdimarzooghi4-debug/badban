import { describe, expect, it, vi, afterEach } from "vitest";
import { amount, api, ApiError } from "./api";

afterEach(() => vi.unstubAllGlobals());

describe("formatting", () => {
  it("does not fabricate missing financial values", () => {
    expect(amount(null, "IRR")).toBe("اطلاعات موجود نیست");
    expect(amount("1234567.00", "IRR")).toBe("1٬234٬567 IRR");
    expect(amount("1234567.50", "IRR")).toBe("1٬234٬567٫5 IRR");
  });
  it("never converts malformed amounts to zero", () => {
    expect(amount("foo")).toBe("اطلاعات نامعتبر");
  });
});

describe("backend client", () => {
  it("rejects unauthenticated calls before network I/O", async () => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    await expect(api("/api/v1/applicant/financial-case", "")).rejects.toBeInstanceOf(ApiError);
    expect(fetch).not.toHaveBeenCalled();
  });
  it("never requests an arbitrary external URL", async () => {
    await expect(api("https://attacker.example/api", "token")).rejects.toThrow("نامعتبر");
  });
  it("forwards bearer in memory only and fails closed on a 403", async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: false, status: 403 });
    vi.stubGlobal("fetch", fetch);
    await expect(api("/api/v1/lender/providers", "token")).rejects.toMatchObject({ status: 403 });
    expect(fetch.mock.calls[0][1]).toMatchObject({ credentials: "omit", cache: "no-store" });
  });
});
