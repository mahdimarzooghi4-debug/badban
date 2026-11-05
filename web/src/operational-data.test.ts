import { describe, expect, it } from "vitest";
import {
  adminServiceQueuePath, allowedAdminServices, institutionCasePath, requireUuid,
  valueOrUnavailable, verifiedBeneficiariesPage, verifiedInstitutionCase,
  verifiedIntakePage, verifiedLenderGuaranteesPage,
} from "./operational-data";
const a="11111111-1111-4111-8111-111111111111", b="22222222-2222-4222-8222-222222222222", c="33333333-3333-4333-8333-333333333333";
const base={program_id:a,participant_id:b,episode_id:c,assets:[],guarantees:[],monthly_pension_entitlements:[],post_exit_support_cases:[],program_return_allocations:[]};
describe("bounded routes",()=>{
 it("builds exact institution and service paths",()=>{
  expect(institutionCasePath(a,b,c)).toBe("/api/v1/support-institution/programs/"+a+"/beneficiaries/"+b+"/episodes/"+c+"/financial-case");
  expect(adminServiceQueuePath("LOAN_GUARANTEE",25,25)).toBe("/api/v1/admin/service-operations/LOAN_GUARANTEE/applicant-requests?limit=25&offset=25");
 });
 it("rejects invalid UUIDs and unbounded pages",()=>{
  expect(()=>requireUuid("../admin")).toThrow();
  expect(()=>institutionCasePath(a,"../admin",c)).toThrow();
  expect(()=>adminServiceQueuePath("LOAN_GUARANTEE",101,0)).toThrow();
  expect(()=>adminServiceQueuePath("MONTHLY_PENSION",25,-1)).toThrow();
 });
});
describe("admin permissions are backend-derived",()=>{
 const workspace={workspace_code:"ADMIN_SERVICE_OPERATIONS",scope_type:"SERVICE",scope_id:a,service_code:"LOAN_GUARANTEE",role_codes:["ROLE_OPERATOR"],capabilities:["READ_APPLICANT_SERVICE_REQUESTS"]};
 it("shows only service scopes with the exact read capability",()=>{
  expect(allowedAdminServices([workspace])).toEqual(["LOAN_GUARANTEE"]);
  expect(allowedAdminServices([{...workspace,capabilities:[]}])).toEqual([]);
  expect(allowedAdminServices([{...workspace,scope_type:"GLOBAL"}])).toEqual([]);
  expect(allowedAdminServices([{...workspace,scope_id:null}])).toEqual([]);
 });
});
describe("institution financial-case contract",()=>{
 it("accepts exact scope and preserves unknown versus zero",()=>{
  expect(verifiedInstitutionCase(base,a,b,c)).toEqual(base);
  expect(valueOrUnavailable(null)).toBe("اطلاعات موجود نیست");
  expect(valueOrUnavailable("0")).toBe("0");
 });
 it("rejects cross-program/person/episode and missing collections",()=>{
  expect(()=>verifiedInstitutionCase(base,b,b,c)).toThrow();
  expect(()=>verifiedInstitutionCase(base,a,a,c)).toThrow();
  expect(()=>verifiedInstitutionCase(base,a,b,a)).toThrow();
  expect(()=>verifiedInstitutionCase({...base,assets:null},a,b,c)).toThrow();
 });
 it("validates asset ownership, nested valuation and money",()=>{
  const asset={id:a,asset_code:"CASH",asset_name:"وجه نقد",ownership_funding_type:"PROGRAM_ATTRIBUTED",quantity:"0",unit_code:"IRR",lifecycle_status:"RECORDED",valuation_observations:[]};
  expect(verifiedInstitutionCase({...base,assets:[asset]},a,b,c).assets[0].ownership_funding_type).toBe("PROGRAM_ATTRIBUTED");
  expect(()=>verifiedInstitutionCase({...base,assets:[{...asset,quantity:"NaN"}]},a,b,c)).toThrow();
  const valuation={id:b,source_name:"source",source_reference:"ref",source_version_reference:null,observed_at:"2026-01-01T00:00:00Z",freshness_status:"CURRENT",valuation_currency:"IRR",unit_price:"1",gross_market_value:"2",valid_until:null};
  expect(verifiedInstitutionCase({...base,assets:[{...asset,valuation_observations:[valuation]}]},a,b,c).assets).toHaveLength(1);
  expect(()=>verifiedInstitutionCase({...base,assets:[{...asset,valuation_observations:[{...valuation,observed_at:"yesterday"}]}]},a,b,c)).toThrow();
 });
 it("rejects malformed guarantee and benefit records",()=>{
  const g={id:a,provider_id:b,state:"REQUESTED",requested_principal:"100",reserved_guarantee_amount:null,issued_guarantee_amount:null,current_guarantee_exposure:"0",guarantee_mode:"STANDARD",currency:"IRR",loan_state:null,outstanding_principal:null,loan_currency:null,last_synced_at:null,reconciliation_status:null};
  expect(verifiedInstitutionCase({...base,guarantees:[g]},a,b,c).guarantees).toHaveLength(1);
  expect(()=>verifiedInstitutionCase({...base,guarantees:[{...g,outstanding_principal:"2",loan_currency:null}]},a,b,c)).toThrow();
  const p={id:a,period_reference:"2026-01",amount:"10",currency:"IRR",lifecycle_status:"APPROVED",approved_at:null};
  expect(()=>verifiedInstitutionCase({...base,monthly_pension_entitlements:[{...p,amount:"NaN"}]},a,b,c)).toThrow();
 });
});
describe("beneficiary and lender scopes",()=>{
 it("checks program and page before displaying beneficiaries",()=>{
  const page={program_id:a,items:[{participant_id:b,episode_id:c,participation_status:"ACTIVE",consent_state:"RECORDED",started_at:"2026-01-01T00:00:00Z",ended_at:null}],limit:50,offset:0};
  expect(verifiedBeneficiariesPage(page,a).items).toHaveLength(1);
  expect(()=>verifiedBeneficiariesPage(page,b)).toThrow();
 });
 it("checks provider and all reported monetary fields",()=>{
  const item={guarantee_case_id:c,case_state:"ACTIVE",requested_principal:"10",reserved_guarantee_amount:null,issued_guarantee_amount:null,current_guarantee_exposure:"0",guarantee_mode:"STANDARD",currency:"IRR",loan_state:null,original_principal:null,outstanding_principal:null,loan_currency:null,reservation_expires_at:null,disbursed_at:null,settled_at:null,last_synced_at:null};
  expect(verifiedLenderGuaranteesPage({provider_id:a,items:[item],limit:50,offset:0},a).items).toHaveLength(1);
  expect(()=>verifiedLenderGuaranteesPage({provider_id:b,items:[item],limit:50,offset:0},a)).toThrow();
 });
});
describe("admin request queue",()=>{
 const item={id:a,participant_id:b,service_code:"LOAN_GUARANTEE",status:"RECEIVED",submitted_at:"2026-01-01T00:00:00Z"};
 const response={service_code:"LOAN_GUARANTEE",observed_at:"2026-01-02T00:00:00Z",items:[item],limit:25,offset:25};
 it("accepts only exact service, RECEIVED and selected page",()=>{
  expect(verifiedIntakePage(response,"LOAN_GUARANTEE",25,25).items).toHaveLength(1);
  expect(()=>verifiedIntakePage(response,"MONTHLY_PENSION",25,25)).toThrow();
  expect(()=>verifiedIntakePage(response,"LOAN_GUARANTEE",0,25)).toThrow();
  expect(()=>verifiedIntakePage({...response,items:[{...item,status:"APPROVED"}]},"LOAN_GUARANTEE",25,25)).toThrow();
 });
});
