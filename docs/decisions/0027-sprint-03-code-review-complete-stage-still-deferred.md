# Decision 0027 — Sprint 03 Code Review Complete; Stage Still Deferred

- **Status:** Accepted
- **Date:** 2026-10-06
- **Scope:** Sprint 03 / Code Review Gate / Bounded External-Lender Pilot
- **Depends on:** Decision 0023; Decision 0026; Sprint 03; PR #4

## Decision

Sprint 03 Code Review is complete for the Decision 0026-authorized scope:

- BL-008 Maker-Checker / ApprovalRequest;
- BL-012 Immutable Valuation Observation;
- BL-030 Append-Only Journal Engine.

PR #4 was reviewed and merged to `main` after the blocking reversal-idempotency finding was resolved and CI was green.

## Reviewed Outcome

The merged Sprint 03 implementation provides:

- maker-checker ApprovalRequest lifecycle with self-approval prevention;
- payload-hash and target-version binding;
- immutable valuation observations with exact-decimal arithmetic and explicit freshness inputs;
- no valuation-driven mutation of Asset Position market value;
- no valuation-created journal posting;
- append-only balanced journal entries/postings;
- idempotent posting and reversal behavior;
- linked reversal without mutation of the original entry;
- query-only journal reads with no generic arbitrary balance-mutation API;
- database-level immutability protections and migrations.

## Review Evidence

At reviewed PR head `2d3a0603cb5f3be7ce8d0a0a2e349dc8ecd2f03f`:

- CI run #103 succeeded;
- the blocking reversal retry-idempotency finding was resolved;
- regression coverage proves identical retry returns the same reversal;
- a different key for an already reversed journal remains rejected.

The squash merge commit on `main` is:

`ef15e7f9df1950ab3e1dc3e3a6da4b99b80b13f7`.

## Scope Guard

Sprint 03 does not authorize or implement:

- Policy Pack lifecycle;
- PolicyResolver / DecisionSnapshot;
- guarantee capacity;
- Portfolio Risk Snapshot;
- provider/product/legal authorization registry;
- guarantee request/reservation/issuance;
- lender/guarantee adapters;
- external loan mirror;
- claim/recovery;
- return allocation;
- Direct Lending;
- real-money use.

## Stage Boundary

Decision 0023 remains in force.

Stage is still deferred because the environment is unavailable. Sprint 03 joins the accumulated future Stage candidate and does not claim Stage validation.

## Consequence

Sprint 03 Code and Code Review are complete on `main`.

The next permitted action is Sprint 04 planning from the accepted Product Backlog and now-satisfied dependencies.
