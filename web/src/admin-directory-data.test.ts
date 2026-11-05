import { describe, expect, it } from "vitest";
import {
  adminDirectoryPath,
  verifiedHumanIdentityPage,
  verifiedLegalEntityPage,
  verifiedProgramPage,
} from "./admin-directory-data";

const identity = "11111111-1111-4111-8111-111111111111";
const entity = "22222222-2222-4222-8222-222222222222";
const program = "33333333-3333-4333-8333-333333333333";
const observed = "2026-11-05T10:00:00Z";
const base = { observed_at: observed, limit: 25, offset: 0 };

describe("admin reference directory contracts", () => {
  it("builds only bounded API paths", () => {
    expect(adminDirectoryPath("identities")).toBe(
      "/api/v1/admin/directory/identities?limit=25&offset=0",
    );
    expect(adminDirectoryPath("legal-entities", 50, 25)).toBe(
      "/api/v1/admin/directory/legal-entities?limit=50&offset=25",
    );
    expect(adminDirectoryPath("programs")).toBe(
      "/api/v1/admin/directory/programs?limit=25&offset=0",
    );
    expect(() => adminDirectoryPath("identities", 101, 0)).toThrow();
    expect(() => adminDirectoryPath("programs", 25, -1)).toThrow();
  });

  it("accepts minimal human identities and rejects participant identities", () => {
    const response = {
      ...base,
      items: [{
        identity_id: identity,
        identity_type: "GOVERNANCE",
        status: "ACTIVE",
        created_at: observed,
      }],
    };
    expect(verifiedHumanIdentityPage(response, 25, 0).items).toHaveLength(1);
    expect(() => verifiedHumanIdentityPage({
      ...response,
      items: [{ ...response.items[0], identity_type: "PARTICIPANT" }],
    }, 25, 0)).toThrow();
    expect(() => verifiedHumanIdentityPage({
      ...response,
      items: [{ ...response.items[0], external_subject: "sensitive-subject" }],
    }, 25, 0)).toThrow();
  });

  it("validates legal entity metadata and rejects registration identifiers", () => {
    const response = {
      ...base,
      items: [{
        legal_entity_id: entity,
        legal_name: "Reference Entity",
        entity_type: "NONPROFIT",
        status: "ACTIVE",
        version: 1,
        created_at: observed,
      }],
    };
    expect(verifiedLegalEntityPage(response, 25, 0).items).toHaveLength(1);
    expect(() => verifiedLegalEntityPage({
      ...response,
      items: [{ ...response.items[0], registration_identifier: "private-id" }],
    }, 25, 0)).toThrow();
  });

  it("validates program references and excludes creator and beneficiary fields", () => {
    const response = {
      ...base,
      items: [{
        program_id: program,
        code: "PROGRAM-A",
        name: "Program A",
        status: "ACTIVE",
        legal_entity_id: entity,
        version: 2,
        created_at: observed,
      }],
    };
    expect(verifiedProgramPage(response, 25, 0).items).toHaveLength(1);
    expect(() => verifiedProgramPage({
      ...response,
      items: [{ ...response.items[0], created_by: identity }],
    }, 25, 0)).toThrow();
    expect(() => verifiedProgramPage({
      ...response,
      items: [{ ...response.items[0], legal_entity_id: "bad" }],
    }, 25, 0)).toThrow();
  });

  it("rejects stale page metadata, malformed UUIDs and naive timestamps", () => {
    const identityResponse = {
      ...base,
      items: [{
        identity_id: identity,
        identity_type: "STAFF",
        status: "ACTIVE",
        created_at: observed,
      }],
    };
    expect(() => verifiedHumanIdentityPage({
      ...identityResponse,
      offset: 25,
    }, 25, 0)).toThrow();
    expect(() => verifiedHumanIdentityPage({
      ...identityResponse,
      items: [{ ...identityResponse.items[0], identity_id: "not-a-uuid" }],
    }, 25, 0)).toThrow();
    expect(() => verifiedHumanIdentityPage({
      ...identityResponse,
      items: [{ ...identityResponse.items[0], created_at: "2026-11-05T10:00:00" }],
    }, 25, 0)).toThrow();
  });
});
