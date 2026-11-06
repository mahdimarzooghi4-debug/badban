import { describe, expect, it } from "vitest";
import {
  financialHistoryPath,
  financialStatementPath,
  verifiedFinancialHistoryPage,
  verifiedProgramStatement,
} from "./institution-ledger-data";

const program = "11111111-1111-4111-8111-111111111111";
const legalEntity = "22222222-2222-4222-8222-222222222222";
const journal = "33333333-3333-4333-8333-333333333333";
const now = "2026-11-06T10:00:00Z";

function historyPayload() {
  return {
    source_type: "INTERNAL_BADBAN_POSTED_JOURNAL",
    program_id: program,
    legal_entity_id: legalEntity,
    snapshot_at: now,
    limit: 25,
    offset: 0,
    total_entries: 1,
    items: [{
      id: journal,
      state: "POSTED",
      business_event_type: "PROGRAM_CAPITAL_RECOGNIZED",
      currency: "IRR",
      effective_at: now,
      posted_at: now,
      reversal_of_entry_id: null,
      policy_version_reference: "policy:v1",
      posting_template_reference: "template:v1",
      evidence_reference: "evidence:source-1",
      postings: [{
        account_code: "1000.SETTLEMENT_CASH_CONTROL",
        account_name: "Settlement cash control",
        account_class: "CONTROLLED_ASSET",
        economic_owner_type: "PROGRAM",
        normal_balance: "DEBIT",
        ledger_layer: "MONETARY",
        debit_amount: "10.000000000000000000",
        credit_amount: "0.000000000000000000",
        currency: "IRR",
      }, {
        account_code: "2030.PROGRAM_CAPITAL_BALANCE",
        account_name: "Program capital balance",
        account_class: "OWNER_OR_ENTITLEMENT_BALANCE",
        economic_owner_type: "PROGRAM",
        normal_balance: "CREDIT",
        ledger_layer: "MONETARY",
        debit_amount: "0.000000000000000000",
        credit_amount: "10.000000000000000000",
        currency: "IRR",
      }],
    }],
  };
}
function statementPayload() {
  return {
    source_type: "INTERNAL_BADBAN_POSTED_JOURNAL",
    program_id: program,
    legal_entity_id: legalEntity,
    snapshot_at: now,
    received_at: now,
    source_reference: "badban:journal-postings:program",
    schema_version: "reconciliation-source-v2",
    contract_version: "internal-posted-journal-v1",
    mapping_version: "posted-account-normal-balance-v1",
    content_hash: "a".repeat(64),
    evidence_references: ["journal-entry:" + journal],
    limit: 25,
    offset: 0,
    total_rows: 1,
    items: [{
      account_code: "2000.PARTICIPANT_PAYABLE_BALANCE",
      account_name: "Participant payable balance",
      account_class: "OWNER_OR_ENTITLEMENT_BALANCE",
      currency: "IRR",
      legal_entity_id: legalEntity,
      economic_owner_type: "PARTICIPANT",
      ledger_layer: "MONETARY",
      normal_balance: "CREDIT",
      balance: "25.000000000000000000",
    }],
  };
}

describe("supporting institution ledger read contracts", () => {
  it("builds only exact-program read paths and rejects invalid pagination or IDs", () => {
    expect(financialHistoryPath(program, 25, 0, now)).toContain(
      "/" + program + "/financial-history?limit=25&offset=0&snapshot_at=" + encodeURIComponent(now),
    );
    expect(financialStatementPath(program, 50, 50, now)).toContain(
      "/" + program + "/financial-statement?limit=50&offset=50&snapshot_at=" + encodeURIComponent(now),
    );
    expect(() => financialHistoryPath("not-a-uuid")).toThrow();
    expect(() => financialStatementPath(program, 101, 0)).toThrow();
  });

  it("validates POSTED complete history and rejects private posting dimensions", () => {
    const result = verifiedFinancialHistoryPage(historyPayload(), program, 25, 0, now);
    expect(result.items).toHaveLength(1);
    const invalid = historyPayload();
    (invalid.items[0].postings[0] as Record<string, unknown>).participant_id = journal;
    expect(() => verifiedFinancialHistoryPage(invalid, program, 25, 0)).toThrow("ابعاد خصوصی");
  });

  it("rejects a history page for a different program or a non-POSTED entry", () => {
    const wrongProgram = historyPayload();
    wrongProgram.program_id = legalEntity;
    expect(() => verifiedFinancialHistoryPage(wrongProgram, program, 25, 0)).toThrow();
    const unposted = historyPayload();
    unposted.items[0].state = "PREPARED";
    expect(() => verifiedFinancialHistoryPage(unposted, program, 25, 0)).toThrow();
  });

  it("validates program statement aggregation without participant identifiers", () => {
    const result = verifiedProgramStatement(statementPayload(), program, 25, 0, now);
    expect(result.items[0].balance).toBe("25.000000000000000000");
    const invalid = statementPayload();
    (invalid.items[0] as unknown as Record<string, unknown>).participant_id = journal;
    expect(() => verifiedProgramStatement(invalid, program, 25, 0)).toThrow("شناسه خصوصی");
  });

  it("rejects a statement with missing evidence or a mismatched legal entity", () => {
    const noEvidence = statementPayload();
    noEvidence.evidence_references = [];
    expect(() => verifiedProgramStatement(noEvidence, program, 25, 0)).toThrow();
    const wrongEntity = statementPayload();
    wrongEntity.items[0].legal_entity_id = program;
    expect(() => verifiedProgramStatement(wrongEntity, program, 25, 0)).toThrow();
    expect(() => verifiedProgramStatement(statementPayload(), program, 25, 0, "2026-11-06T11:00:00Z")).toThrow();
  });
});
