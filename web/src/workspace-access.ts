import type { CurrentIdentity, RoleGrant } from "./api";

export type Surface = "individual" | "institution" | "lender" | "admin";
const uuidPattern = /^[a-f\d]{8}-[a-f\d]{4}-[1-8][a-f\d]{3}-[89ab][a-f\d]{3}-[a-f\d]{12}$/i;
function record(value: unknown): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) throw new Error("ساختار مجوزهای حساب معتبر نیست.");
  return value as Record<string, unknown>;
}
function validUuid(value: unknown): value is string {
  return typeof value === "string" && uuidPattern.test(value);
}
function strings(value: unknown): value is string[] {
  return Array.isArray(value) && value.every(item => typeof item === "string");
}
function verifiedIdentity(value: unknown): CurrentIdentity {
  const identity = record(value);
  if (!validUuid(identity.identity_id) || typeof identity.external_subject !== "string" ||
      !identity.external_subject || typeof identity.identity_type !== "string" || !identity.identity_type) {
    throw new Error("پاسخ هویت جاری معتبر نیست.");
  }
  return identity as unknown as CurrentIdentity;
}
function verifiedGrants(value: unknown): RoleGrant[] {
  if (!Array.isArray(value)) throw new Error("فهرست مجوزهای فعال معتبر نیست.");
  return value.map(raw => {
    const grant = record(raw);
    if (!validUuid(grant.id) || typeof grant.role_code !== "string" || !grant.role_code ||
        typeof grant.scope_type !== "string" || !(grant.scope_id === null || validUuid(grant.scope_id)) ||
        typeof grant.valid_from !== "string" || Number.isNaN(Date.parse(grant.valid_from)) ||
        !(grant.valid_until === null || (typeof grant.valid_until === "string" && !Number.isNaN(Date.parse(grant.valid_until)))) ||
        grant.status !== "ACTIVE" || !Number.isInteger(grant.version) || (grant.version as number) < 1) {
      throw new Error("یکی از مجوزهای حساب ناقص یا ناسازگار است.");
    }
    return grant as unknown as RoleGrant;
  });
}
function hasAdminWorkspace(value: unknown): boolean {
  const root = record(value);
  if (!Array.isArray(root.items)) throw new Error("فهرست محیط‌های مدیریتی معتبر نیست.");
  return root.items.some(raw => {
    const item = record(raw);
    if (typeof item.workspace_code !== "string" || !strings(item.role_codes) ||
        !strings(item.capabilities) || typeof item.scope_type !== "string" ||
        !(item.scope_id === null || validUuid(item.scope_id))) return false;
    if (item.workspace_code === "ADMIN_SERVICE_OPERATIONS") {
      return item.scope_type === "SERVICE" && validUuid(item.scope_id) &&
        item.role_codes.length > 0 && item.capabilities.includes("READ_WORK_QUEUE");
    }
    if (item.scope_type !== "GLOBAL" || item.scope_id !== null ||
        !item.role_codes.includes("GOVERNANCE_APPROVER")) return false;
    if (item.workspace_code === "ADMIN_ACCESS_GOVERNANCE") {
      return item.capabilities.some(capability => capability.startsWith("MANAGE_"));
    }
    if (item.workspace_code === "ADMIN_BENEFIT_LINEAGE_REVIEW") {
      return item.capabilities.includes("READ_LEGACY_BENEFIT_LINEAGE_REVIEW_QUEUE");
    }
    return false;
  });
}
export function deriveAvailableSurfaces(identityInput: unknown, grantsInput: unknown, workspacesInput: unknown): Surface[] {
  const identity = verifiedIdentity(identityInput);
  const grants = verifiedGrants(grantsInput);
  const available: Surface[] = [];
  if (identity.identity_type === "PARTICIPANT") available.push("individual");
  if (grants.some(grant => grant.role_code === "SUPPORT_INSTITUTION_OPERATOR" &&
      grant.scope_type === "PROGRAM" && validUuid(grant.scope_id))) available.push("institution");
  if (grants.some(grant => grant.role_code === "LENDER_OPERATOR" &&
      grant.scope_type === "PROVIDER" && validUuid(grant.scope_id))) available.push("lender");
  if (hasAdminWorkspace(workspacesInput)) available.push("admin");
  return available;
}
