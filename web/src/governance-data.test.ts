import { describe, expect, it } from "vitest";
import { governanceQueuePath, verifiedGrantPage, verifiedBenefitReviewPage } from "./governance-data";
const a="11111111-1111-4111-8111-111111111111",b="22222222-2222-4222-8222-222222222222";
describe("governance route boundaries",()=>{
 it("constructs only known governance read routes",()=>{
  expect(governanceQueuePath("support-institution","REQUESTED",25,0)).toBe("/api/v1/admin/support-institution/grants?status=REQUESTED&limit=25&offset=0");
  expect(governanceQueuePath("lender","ACTIVE",25,25)).toBe("/api/v1/admin/lender-access/grants?status=ACTIVE&limit=25&offset=25");
  expect(governanceQueuePath("benefit-lineage","REJECTED",25,0)).toBe("/api/v1/admin/benefit-lineage/reviews?status=REJECTED&limit=25&offset=0");
  expect(()=>governanceQueuePath("lender","APPROVED" as never)).toThrow();
  expect(()=>governanceQueuePath("benefit-lineage","ACTIVE" as never)).toThrow();
  expect(()=>governanceQueuePath("lender","REQUESTED",101,0)).toThrow();
 });
});
describe("scoped role grant queue",()=>{
 const grant={id:a,identity_id:b,role_code:"ROLE_SUPPORT_INSTITUTION_OPERATOR",scope_type:"PROGRAM",scope_id:a,
  valid_from:"2026-01-01T00:00:00Z",valid_until:null,status:"REQUESTED",granted_by:null,reason_ref:"ref:one",version:1};
 it("accepts only exact status, role and scope",()=>{
  const page={items:[grant],status:"REQUESTED",limit:25,offset:0};
  expect(verifiedGrantPage(page,"REQUESTED","ROLE_SUPPORT_INSTITUTION_OPERATOR","PROGRAM",25,0).items).toHaveLength(1);
  expect(()=>verifiedGrantPage(page,"ACTIVE","ROLE_SUPPORT_INSTITUTION_OPERATOR","PROGRAM",25,0)).toThrow();
  expect(()=>verifiedGrantPage(page,"REQUESTED","ROLE_LENDER_OPERATOR","PROGRAM",25,0)).toThrow();
  expect(()=>verifiedGrantPage(page,"REQUESTED","ROLE_SUPPORT_INSTITUTION_OPERATOR","PROVIDER",25,0)).toThrow();
  expect(()=>verifiedGrantPage({...page,offset:25},"REQUESTED","ROLE_SUPPORT_INSTITUTION_OPERATOR","PROGRAM",25,0)).toThrow();
 });
 it("rejects malformed grants and retains nullable expiry",()=>{
  const page={items:[grant],status:"REQUESTED",limit:25,offset:0};
  expect(verifiedGrantPage(page,"REQUESTED","ROLE_SUPPORT_INSTITUTION_OPERATOR","PROGRAM",25,0).items[0].valid_until).toBeNull();
  expect(()=>verifiedGrantPage({...page,items:[{...grant,scope_id:"bad"}]},"REQUESTED","ROLE_SUPPORT_INSTITUTION_OPERATOR","PROGRAM",25,0)).toThrow();
  expect(()=>verifiedGrantPage({...page,items:[{...grant,valid_from:"yesterday"}]},"REQUESTED","ROLE_SUPPORT_INSTITUTION_OPERATOR","PROGRAM",25,0)).toThrow();
 });
});
describe("benefit lineage review queue",()=>{
 const item={id:a,benefit_type:"MONTHLY_PENSION",benefit_record_id:b,participant_id:a,program_id:b,
  participation_episode_id:a,evidence_reference:"evidence:one",reason_reference:"reason:one",status:"REQUESTED",
  requested_by:b,reviewed_by:null,reviewed_at:null,review_reason_reference:null,created_at:"2026-01-01T00:00:00Z"};
 it("validates exact review status and immutable lineage identifiers",()=>{
  const page={items:[item],status:"REQUESTED",limit:25,offset:0};
  expect(verifiedBenefitReviewPage(page,"REQUESTED",25,0).items).toHaveLength(1);
  expect(()=>verifiedBenefitReviewPage(page,"APPROVED",25,0)).toThrow();
  expect(()=>verifiedBenefitReviewPage({...page,items:[{...item,participation_episode_id:"bad"}]},"REQUESTED",25,0)).toThrow();
  expect(()=>verifiedBenefitReviewPage({...page,items:[{...item,evidence_reference:""}]},"REQUESTED",25,0)).toThrow();
 });
});
