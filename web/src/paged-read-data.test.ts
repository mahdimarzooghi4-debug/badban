import { describe, expect, it } from "vitest";
import {
  READ_PAGE_SIZE, checkedReadPage, nextPageOffset, previousPageOffset, readPagePath,
  verifiedProgramsPage, verifiedProvidersPage, verifiedPagedBeneficiaries, verifiedPagedGuarantees,
} from "./paged-read-data";

const program = "11111111-1111-4111-8111-111111111111";
const provider = "22222222-2222-4222-8222-222222222222";
const person = "33333333-3333-4333-8333-333333333333";
const episode = "44444444-4444-4444-8444-444444444444";
const guaranteeId = "55555555-5555-4555-8555-555555555555";

describe("exact backend pagination routes", () => {
  it("builds all four read-only endpoints with explicit page coordinates", () => {
    expect(readPagePath("programs",25,50)).toBe("/api/v1/support-institution/programs?limit=25&offset=50");
    expect(readPagePath("beneficiaries",25,25,program)).toBe("/api/v1/support-institution/programs/"+program+"/beneficiaries?limit=25&offset=25");
    expect(readPagePath("providers",25,0)).toBe("/api/v1/lender/providers?limit=25&offset=0");
    expect(readPagePath("guarantees",25,75,provider)).toBe("/api/v1/lender/providers/"+provider+"/guarantees?limit=25&offset=75");
  });
  it("rejects bad ID, parameter injection, invalid range, unsafe integers", () => {
    expect(()=>readPagePath("beneficiaries",25,0,"../other")).toThrow();
    expect(()=>readPagePath("guarantees",25,0,program+"?other=1")).toThrow();
    expect(()=>readPagePath("providers",25,0,provider)).toThrow();
    expect(()=>readPagePath("programs",25,0,program)).toThrow();
    expect(()=>readPagePath("providers",101,0)).toThrow();
    expect(()=>checkedReadPage(25,-1)).toThrow();
    expect(()=>checkedReadPage(25,Number.MAX_SAFE_INTEGER)).toThrow();
    expect(()=>checkedReadPage(25,0.5)).toThrow();
  });
  it("does not manufacture an unknown total count", () => {
    expect(nextPageOffset(0,READ_PAGE_SIZE)).toBe(READ_PAGE_SIZE);
    expect(nextPageOffset(25,2)).toBeNull();
    expect(nextPageOffset(25,0)).toBeNull();
    expect(previousPageOffset(25)).toBe(0);
    expect(previousPageOffset(0)).toBe(0);
    expect(()=>nextPageOffset(0,26)).toThrow();
  });
});
describe("authorized programs and lenders",()=>{
  const prog={program_id:program,code:"PROGRAM_1",name:"برنامه یک",status:"ACTIVE"};
  const prov={provider_id:provider,provider_code:"P001",display_name:"صندوق یک"};
  it("validates exact page bounds and active program records",()=>{
    const page={items:[prog],limit:25,offset:25};
    expect(verifiedProgramsPage(page,25,25).items[0]).toEqual(prog);
    expect(()=>verifiedProgramsPage(page,25,0)).toThrow();
    expect(()=>verifiedProgramsPage({...page,limit:50},25,25)).toThrow();
    expect(()=>verifiedProgramsPage({...page,items:[{...prog,status:"PENDING"}]},25,25)).toThrow();
    expect(()=>verifiedProgramsPage({...page,items:[prog,prog]},25,25)).toThrow();
  });
  it("validates provider rows and rejects duplicate or forged pages",()=>{
    const page={items:[prov],limit:25,offset:0};
    expect(verifiedProvidersPage(page,25,0).items[0]).toEqual(prov);
    expect(()=>verifiedProvidersPage({...page,offset:25},25,0)).toThrow();
    expect(()=>verifiedProvidersPage({...page,items:[{...prov,provider_id:"bad"}]},25,0)).toThrow();
    expect(()=>verifiedProvidersPage({...page,items:[prov,prov]},25,0)).toThrow();
  });
});
describe("program and provider scoped child pages",()=>{
  const beneficiary={participant_id:person,episode_id:episode,participation_status:"ACTIVE",
    consent_state:"RECORDED",started_at:"2026-01-01T00:00:00Z",ended_at:null};
  const guarantee={guarantee_case_id:guaranteeId,case_state:"REQUESTED",requested_principal:"100",
    reserved_guarantee_amount:null,issued_guarantee_amount:null,current_guarantee_exposure:"0",
    guarantee_mode:"STANDARD",currency:"IRR",loan_state:null,original_principal:null,
    outstanding_principal:null,loan_currency:null,reservation_expires_at:null,disbursed_at:null,
    settled_at:null,last_synced_at:null};
  it("checks requested parent program and exact child page",()=>{
    const page={program_id:program,items:[beneficiary],limit:25,offset:25};
    expect(verifiedPagedBeneficiaries(page,program,25,25).items[0].episode_id).toBe(episode);
    expect(()=>verifiedPagedBeneficiaries({...page,program_id:provider},program,25,25)).toThrow();
    expect(()=>verifiedPagedBeneficiaries({...page,offset:0},program,25,25)).toThrow();
    expect(()=>verifiedPagedBeneficiaries({...page,items:[beneficiary,beneficiary]},program,25,25)).toThrow();
  });
  it("checks exact provider and rejects malformed financial amounts",()=>{
    const page={provider_id:provider,items:[guarantee],limit:25,offset:25};
    expect(verifiedPagedGuarantees(page,provider,25,25).items[0].guarantee_case_id).toBe(guaranteeId);
    expect(()=>verifiedPagedGuarantees({...page,provider_id:program},provider,25,25)).toThrow();
    expect(()=>verifiedPagedGuarantees({...page,offset:0},provider,25,25)).toThrow();
    expect(()=>verifiedPagedGuarantees({...page,items:[{...guarantee,outstanding_principal:"NaN"}]},provider,25,25)).toThrow();
    expect(()=>verifiedPagedGuarantees({...page,items:[guarantee,guarantee]},provider,25,25)).toThrow();
  });
});
