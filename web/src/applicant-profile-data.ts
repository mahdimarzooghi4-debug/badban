import { api } from "./api";

export type ApplicantProfile = { participant_id: string; lifecycle_status: string };

const uuidPattern = /^[\da-f]{8}-[\da-f]{4}-[1-8][\da-f]{3}-[89ab][\da-f]{3}-[\da-f]{12}$/i;
const storedState = /^[A-Z][A-Z0-9_]{0,39}$/;

export function validateApplicantProfile(raw: unknown): ApplicantProfile {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    throw new Error("پروفایل حساب معتبر نیست.");
  }
  const record = raw as Record<string, unknown>;
  if (
    typeof record.participant_id !== "string" || !uuidPattern.test(record.participant_id) ||
    typeof record.lifecycle_status !== "string" || !storedState.test(record.lifecycle_status)
  ) {
    throw new Error("اطلاعات پروفایل با قرارداد بک‌اند مطابقت ندارد.");
  }
  // Whitelist only the two self-scoped fields. Never expose the national ID,
  // OIDC subject or extraneous backend metadata to the account interface.
  return {
    participant_id: record.participant_id,
    lifecycle_status: record.lifecycle_status,
  };
}

export async function loadApplicantProfile(token: string): Promise<ApplicantProfile> {
  const value = await api<unknown>("/api/v1/applicant/participant", token);
  return validateApplicantProfile(value);
}
