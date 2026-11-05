import { describe, expect, it } from "vitest";
import { deriveAvailableSurfaces } from "./workspace-access";

const identity={identity_id:"11111111-1111-4111-8111-111111111111",external_subject:"subject",identity_type:"STAFF"};
const scope="22222222-2222-4222-8222-222222222222";
function grant(role_code:string,scope_type:string,scope_id:string|null=scope,status="ACTIVE") {
 return {id:"33333333-3333-4333-8333-333333333333",role_code,scope_type,scope_id,valid_from:"2026-01-01T00:00:00Z",valid_until:null,status,version:1};
}
const emptyWorkspaces={items:[]};
const adminWorkspaces={items:[{workspace_code:"ADMIN_ACCESS_GOVERNANCE",scope_type:"GLOBAL",scope_id:null,service_code:null,role_codes:["GOVERNANCE_APPROVER"],capabilities:["MANAGE_SUPPORT_INSTITUTION_GRANTS"]}]};
describe("role-derived workspace entry",()=>{
 it("shows only the individual surface for a participant identity without grants",()=>{
  expect(deriveAvailableSurfaces({...identity,identity_type:"PARTICIPANT"},[],emptyWorkspaces)).toEqual(["individual"]);
 });
 it("requires the exact PROGRAM scope for a supporting institution",()=>{
  expect(deriveAvailableSurfaces(identity,[grant("SUPPORT_INSTITUTION_OPERATOR","PROGRAM")],emptyWorkspaces)).toEqual(["institution"]);
  expect(deriveAvailableSurfaces(identity,[grant("SUPPORT_INSTITUTION_OPERATOR","GLOBAL",null)],emptyWorkspaces)).toEqual([]);
 });
 it("requires the exact PROVIDER scope for a lender",()=>{
  expect(deriveAvailableSurfaces(identity,[grant("LENDER_OPERATOR","PROVIDER")],emptyWorkspaces)).toEqual(["lender"]);
  expect(deriveAvailableSurfaces(identity,[grant("LENDER_OPERATOR","PROGRAM")],emptyWorkspaces)).toEqual([]);
 });
 it("fails closed on inactive or malformed records and ignores unrelated active roles",()=>{
  expect(()=>deriveAvailableSurfaces(identity,[grant("SUPPORT_INSTITUTION_OPERATOR","PROGRAM",scope,"REVOKED")],emptyWorkspaces)).toThrow();
  expect(deriveAvailableSurfaces(identity,[grant("OPERATIONS","SERVICE")],emptyWorkspaces)).toEqual([]);
  expect(()=>deriveAvailableSurfaces(identity,[grant("LENDER_OPERATOR","PROVIDER","not-a-uuid")],emptyWorkspaces)).toThrow();
 });
 it("shows admin only for a recognized active role-derived workspace",()=>{
  expect(deriveAvailableSurfaces(identity,[],adminWorkspaces)).toEqual(["admin"]);
  expect(deriveAvailableSurfaces(identity,[],{items:[{...adminWorkspaces.items[0],scope_type:"SERVICE",scope_id:scope}]})).toEqual([]);
  expect(deriveAvailableSurfaces(identity,[],{items:[{...adminWorkspaces.items[0],role_codes:["AUDITOR"]}]})).toEqual([]);
 });
 it("combines only the surfaces backed by independently valid identity, grants and admin index",()=>{
  expect(deriveAvailableSurfaces({...identity,identity_type:"PARTICIPANT"},[
    grant("SUPPORT_INSTITUTION_OPERATOR","PROGRAM"),grant("LENDER_OPERATOR","PROVIDER")
  ],adminWorkspaces)).toEqual(["individual","institution","lender","admin"]);
 });
 it("fails closed on malformed identity or grant payloads",()=>{
  expect(()=>deriveAvailableSurfaces({},[],emptyWorkspaces)).toThrow();
  expect(()=>deriveAvailableSurfaces(identity,[{...grant("LENDER_OPERATOR","PROVIDER"),scope_id:"bad"}],emptyWorkspaces)).toThrow();
  expect(()=>deriveAvailableSurfaces(identity,[],{items:"invalid"})).toThrow();
 });
});
