# Sprint 10 — Product Account Taxonomy and Posting Templates

- **Status:** Accepted
- **Date:** 2026-10-07
- **Stage:** Sprint Planning
- **Scope:** bounded external-lender pilot
- **Entry Gate:** Sprint 09 / BL-032 Code + Code Review complete and merged; post-merge CI #232 green
- **Depends on:** BL-030; Decision 0015; Technical 04; Technical 05
- **Code Authorization:** GRANTED BY DECISION 0035

## 1. Sprint Goal

Implement only:

- **BL-031 — Product Account Taxonomy and Posting Templates**

The Sprint establishes the stable Badban product-account vocabulary and internal versioned posting-template registry needed by later financial workflows without inventing statutory accounting mappings or real-money behavior.

## 2. Stable Product Account Taxonomy

Implement exactly the accepted Technical 05 product-level account codes:

### Controlled Asset

- `1000.SETTLEMENT_CASH_CONTROL`
- `1010.PROGRAM_CASH_CONTROL`
- `1020.GUARANTEE_RESERVE_CASH_CONTROL`
- `1030.RECOVERY_CASH_CONTROL`
- `1040.CLAIM_SETTLEMENT_PENDING_RECOVERY_CONTROL`
- `1050.OTHER_APPROVED_CONTROLLED_ASSET`

### Owner / Entitlement Balance

- `2000.PARTICIPANT_PAYABLE_BALANCE`
- `2010.LIVELIHOOD_PAYABLE`
- `2020.FUTURE_FINANCIAL_ENTITLEMENT`
- `2030.PROGRAM_CAPITAL_BALANCE`
- `2040.GUARANTEE_RESERVE_DESIGNATED_BALANCE`
- `2050.SOCIAL_REINVESTMENT_BALANCE`
- `2060.RETURN_CARRY_FORWARD_BALANCE`
- `2070.PARTICIPANT_RELEASE_PAYABLE`
- `2080.PROGRAM_RECYCLABLE_BALANCE`

### Return / Allocation Clearing

- `3000.RECOGNIZED_RETURN_CLEARING`
- `3010.RETURN_ALLOCATION_CLEARING`
- `3020.CAPITAL_GROWTH_CLEARING`

### Loss / Cost Control

- `4000.GUARANTEE_FINAL_RESIDUAL_LOSS`
- `4010.ENFORCEMENT_COST`
- `4020.APPROVED_FINANCIAL_ADJUSTMENT_LOSS`

### Memorandum / Control

- `9000.GUARANTEE_CAPACITY_RESERVED_MEMO`
- `9010.ACTIVE_GUARANTEE_EXPOSURE_MEMO`
- `9020.BACKING_ENCUMBERED_MEMO`
- `9030.CLAIM_APPROVED_PENDING_SETTLEMENT_MEMO`
- `9040.CLAIM_SETTLED_RECOVERY_OPEN_MEMO`
- `9050.EXTERNAL_LOAN_PRINCIPAL_MIRROR_MEMO`
- `9060.EXTERNAL_LOAN_OUTSTANDING_MIRROR_MEMO`

No other production account code is invented by this Sprint.

## 3. Ledger-Layer Boundary

The implementation must preserve three distinct semantic layers:

1. monetary product ledger;
2. memorandum / exposure / encumbrance control;
3. external mirror records.

A memorandum or external mirror item must never be treated as cash, revenue, receivable, payable, or statutory balance merely because it has a product account code.

## 4. Posting Template Registry

Implement an internal immutable/versioned registry for the posting semantics already accepted in Technical 05.

The registry must preserve explicit template code and version and distinguish:

- templates that create monetary journal lines;
- templates that create memorandum/control effects only;
- no-posting/external-mirror events.

The registry must not itself execute a business workflow that is outside the current Sprint.

## 5. Legal-Entity Account Mapping

Implement the Technical 04 relational mapping boundary:

```
Badban Product Account
→ Legal Entity Account Mapping
→ External / Statutory Chart Account
```

Rules:

- mapping is legal-entity specific;
- effective range is explicit;
- historical mapping reference remains stable;
- missing mapping is explicit and must not be guessed;
- no statutory account values are seeded by this Sprint.

## 6. Internal Resolution Contract

Internal helpers must be able to:

- resolve a known product account;
- resolve an exact posting template version;
- validate that requested account codes belong to the permitted layer/template;
- resolve a legal-entity account mapping at an effective time when one exists;
- fail deterministically when a required mapping is absent or ambiguous;
- produce stable references suitable for `JournalEntry.posting_template_reference` and `JournalEntry.account_mapping_reference`.

## 7. Historical Integrity

Changes to current taxonomy metadata, template versions, or legal-entity mappings must not rewrite historical journal references.

Posted journals remain append-only and retain exact references already stored on the journal entry.

## 8. No-Posting Rules

The following accepted Technical 05 events must not automatically create Badban monetary journals:

- valuation observation;
- guarantee capacity calculation;
- guarantee reservation;
- legal guarantee issuance;
- external lender credit approval;
- external loan disbursement itself;
- repayment at the external lender;
- delinquency state;
- claim submission;
- claim rejection;
- release of an external collateral restriction.

They may later create audit, memorandum/control, external mirror, or reconciliation effects in their own authorized workflows.

## 9. Tests

Tests must cover:

- exact canonical account-code seed set;
- account class / ledger-layer integrity;
- migration idempotency and no invented statutory mappings;
- exact template code/version lookup;
- unknown template/account failure;
- no-posting classification for accepted events;
- legal-entity mapping effective-range resolution;
- missing and ambiguous mapping fail-closed behavior;
- historical journal references remain unchanged when mappings/templates later differ;
- no generic HTTP journal-create endpoint is introduced.

## 10. Explicit Non-Goals

No BL-020, BL-016, BL-021, BL-033, provider integration, reservation workflow, real cash movement, statutory chart seeding, Stage pass, QA pass, Release Approval, Production, or real-money behavior.

## 11. Definition of Done

BL-031 is Done through Code Review when the taxonomy persistence, mapping boundary, internal posting-template registry/resolution, migration, and tests are complete; full CI is green; and no accounting/business value outside Accepted Technical 04/05 has been invented.
