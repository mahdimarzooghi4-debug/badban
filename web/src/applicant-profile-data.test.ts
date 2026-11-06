import { afterEach, describe, expect, it, vi } from "vitest";
import { loadApplicantProfile, validateApplicantProfile } from "./applicant-profile-data";

const participant_id = "123e4567-e89b-42d3-a456-426614174000";
const profile = { participant_id, lifecycle_status: "ACTIVE" };

afterEach(() => vi.unstubAllGlobals());

describe("Figma applicant self-profile", () => {
  it("reads only the own-participant GET endpoint with in-memory authentication", async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => profile });
    vi.stubGlobal("fetch", fetch);
    expect(await loadApplicantProfile("token")).toEqual(profile);
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch.mock.calls[0][0]).toBe("/api/v1/applicant/participant");
    expect(fetch.mock.calls[0][1]).toMatchObject({
      credentials: "omit", cache: "no-store", headers: { Authorization: "Bearer token" },
    });
    expect(fetch.mock.calls[0][1].method).toBeUndefined();
  });

  it("rejects missing/forged profile fields and unsupported statuses", () => {
    expect(() => validateApplicantProfile({ ...profile, participant_id: "PR-1405-021" })).toThrow();
    expect(() => validateApplicantProfile({ ...profile, lifecycle_status: "" })).toThrow();
    expect(() => validateApplicantProfile({ ...profile, lifecycle_status: "ACTIVE\nINJECTED" })).toThrow();
    expect(() => validateApplicantProfile({ ...profile, lifecycle_status: "a".repeat(41) })).toThrow();
    expect(() => validateApplicantProfile(null)).toThrow();
    expect(() => validateApplicantProfile([])).toThrow();
  });

  it("never leaks names, national IDs or OIDC subject from extra response fields", () => {
    const result = validateApplicantProfile({
      ...profile, national_id: "1234567890", name: "نام آزمایشی",
      external_subject: "private-issuer-subject", bank_account: "private",
    });
    expect(result).toEqual(profile);
    expect(JSON.stringify(result)).not.toContain("national_id");
    expect(JSON.stringify(result)).not.toContain("private-issuer-subject");
  });

  it("does not manufacture a profile after 404, 403 or missing auth", async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: false, status: 404 });
    vi.stubGlobal("fetch", fetch);
    await expect(loadApplicantProfile("token")).rejects.toMatchObject({ status: 404 });
    await expect(loadApplicantProfile("")).rejects.toMatchObject({ status: 401 });
    expect(fetch).toHaveBeenCalledTimes(1);
  });
});
