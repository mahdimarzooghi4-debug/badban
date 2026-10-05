# Decision 0026 — Sprint 03 Control, Valuation, and Journal Foundations; Code Authorization

- **Status:** Proposed
- **Date:** 2026-10-05
- **Scope:** Sprint 03 / Code Authorization / Bounded External-Lender Pilot
- **Depends on:** Decision 0023; Decision 0025; Sprint 03 Plan

## Proposed Decision

Accept Sprint 03 and authorize Code only for:

- BL-008 Maker-Checker / ApprovalRequest;
- BL-012 Immutable Valuation Observation;
- BL-030 Append-Only Journal Engine.

## Rationale

These items are currently Ready and close prerequisite gaps that block later Policy/Capacity/Risk work:

- BL-013 requires BL-008;
- BL-015 requires BL-012;
- BL-032 requires BL-030.

The original candidate Slice 2 must not be implemented before these dependencies are satisfied.

## Authorized Scope If Accepted

Implementation may include:

- ApprovalRequest persistence/state machine;
- maker/checker separation and checker role/scope validation;
- canonical payload hash and target-version binding;
- approval expiry/reject/cancel behavior;
- immutable valuation observations and explicit freshness inputs;
- trusted valuation-ingest authorization;
- exact-decimal valuation arithmetic;
- append-only journal entries and postings;
- balanced posting validation;
- journal idempotency and linked reversal;
- internal journal services/read models required for the selected scope;
- migrations, tests, audit, CI, and documentation required by these items.

## Explicitly Unauthorized

Acceptance would not authorize:

- Policy Pack lifecycle or activation;
- PolicyResolver / DecisionSnapshot;
- guarantee-capacity calculation/read model;
- Portfolio Risk Snapshot;
- provider/product/legal authorization registry;
- guarantee request/reservation/issuance;
- lender/guarantee adapters;
- external loan mirror;
- claim/recovery;
- return allocation;
- participant exit financial reconciliation;
- generic arbitrary balance-mutation API;
- Direct Lending;
- Stage;
- QA/Testing gate completion;
- Release Approval;
- Production;
- real-money use.

## Hard Invariants

If accepted, Sprint 03 Code must preserve:

1. maker identity != checker identity;
2. approval binds exact payload hash and target version where applicable;
3. approval never bypasses downstream business/policy/legal/risk/reconciliation checks;
4. accepted valuation observations are append-only;
5. valuation never mutates Asset Position into a market-value balance;
6. valuation alone never creates guarantee capacity;
7. valuation creates no monetary journal posting;
8. every POSTED journal balances exactly;
9. no direct mutable balance table;
10. POSTED journal/postings are append-only;
11. corrections occur through linked reversal/adjustment;
12. external-lender principal is not a Badban corporate receivable by default.

## Definition-of-Done Gate

Sprint 03 must satisfy the Accepted Sprint plan, including:

- maker-checker positive/negative tests;
- self-approval prevention;
- payload/target-version invalidation;
- valuation exactness and immutability tests;
- valuation freshness tests without invented production thresholds;
- balanced/unbalanced journal tests;
- journal append-only/reversal/idempotency tests;
- migrations and drift check;
- format/lint/type/security/dependency/container CI gates;
- Code Review complete.

## Stage Boundary

Decision 0023 remains in force.

Sprint 03 may be implemented and reviewed while Stage is unavailable, but Stage validation remains deferred and accumulative.

## Approval Effect

This decision is **Proposed**.

It grants no Code authorization until explicitly Accepted.
