import { describe, expect, it } from "vitest";
import {
  buildGrantRequest, buildGrantRevokeBody, grantMutationPath, grantRequestPath,
} from "./governance-actions";
const identity="11111111-1111-4111-8111-111111111111";
const scope="22222222-2222-4222-8222-222222222222";
const grant="33333333-3333-4333-8333-333333333333";
const draft={identityId:identity,scopeId:scope,validFrom:"2026-11-05T10:00",validUntil:"2026-11-05T12:00",reasonReference:"approval-ref:42"};
describe("grant request command contracts",()=>{
 it("uses exact existing routes for program and provider grants",()=>{
  expect(grantRequestPath("support-institution")).toBe("/api/v1/admin/support-institution/grants");
  expect(grantRequestPath("lender")).toBe("/api/v1/admin/lender-access/grants");
  expect(grantMutationPath("support-institution",grant,"approve")).toBe("/api/v1/admin/support-institution/grants/"+grant+"/approve");
  expect(grantMutationPath("lender",grant,"revoke")).toBe("/api/v1/admin/lender-access/grants/"+grant+"/revoke");
 });
 it("builds exact program request payload and timezone-aware timestamps",()=>{
  const body=buildGrantRequest("support-institution",draft);
  expect(body.identity_id).toBe(identity);
  expect(body.program_id).toBe(scope);
  expect(body.reason_reference).toBe("approval-ref:42");
  expect(typeof body.valid_from).toBe("string");
  expect(String(body.valid_from)).toMatch(/Z$/);
  expect(body.valid_until).toMatch(/Z$/);
  expect("provider_id" in body).toBe(false);
 });
 it("builds exact provider request payload and nullable end time",()=>{
  const body=buildGrantRequest("lender",{...draft,validUntil:""});
  expect(body.provider_id).toBe(scope);
  expect(body.valid_until).toBeNull();
  expect("program_id" in body).toBe(false);
 });
 it("rejects malformed identities, scopes, dates and missing reason references",()=>{
  expect(()=>buildGrantRequest("support-institution",{...draft,identityId:"../admin"})).toThrow();
  expect(()=>buildGrantRequest("lender",{...draft,scopeId:"bad"})).toThrow();
  expect(()=>buildGrantRequest("lender",{...draft,validFrom:""})).toThrow();
  expect(()=>buildGrantRequest("lender",{...draft,validFrom:"not-a-date"})).toThrow();
  expect(()=>buildGrantRequest("lender",{...draft,validUntil:"2026-11-05T09:00"})).toThrow();
  expect(()=>buildGrantRequest("lender",{...draft,reasonReference:"  "})).toThrow();
  expect(()=>buildGrantRequest("lender",{...draft,reasonReference:"x".repeat(256)})).toThrow();
 });
 it("requires a reason for every revocation and confines grant identifiers",()=>{
  expect(buildGrantRevokeBody(" revoke-ref ")).toEqual({reason_reference:"revoke-ref"});
  expect(()=>buildGrantRevokeBody("")).toThrow();
  expect(()=>grantMutationPath("lender","../../me","approve")).toThrow();
 });
});
