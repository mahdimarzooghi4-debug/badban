# Decision 0024 — Sprint 02 Identity and Core Participant / Asset State; Code Authorization

- **Status:** Accepted
- **Date:** 2026-10-05
- **Scope:** Sprint 02 / Code Authorization / Bounded External-Lender Pilot
- **Depends on:** Decision 0023; Sprint 02 — Identity and Core Participant / Asset State

## Decision

Accept Sprint 02 and authorize Code only for the selected Slice 1 backlog items:

- BL-006 Central Identity Integration;
- BL-007 RBAC and Scoped Authorization Engine;
- BL-009 Program and Participation Episode;
- BL-010 Asset Type Registry;
- BL-011 Asset Position and Ownership/Funding Classification;
- BL-044 Audit and Evidence Trace baseline.

## Authorized Scope If Accepted

Implementation may include:

- Keycloak/OIDC-compatible authentication validation;
- Badban identity mapping;
- persisted role grants and deny-by-default scoped authorization;
- Program and ParticipationEpisode write/read models;
- configurable Asset Type Registry;
- Asset Position with exact quantity and explicit ownership/funding classification;
- append-only audit and opaque evidence-reference baseline;
- migrations, API contracts, automated tests, CI updates, and documentation required by the selected items.

## Explicitly Unauthorized

Acceptance would not authorize:

- Maker-Checker / ApprovalRequest;
- valuation;
- Policy Pack;
- guarantee capacity;
- provider/product/legal authorization registry;
- guarantee request/reservation/issuance;
- lender integration or external-loan mirror;
- ledger/risk/reserve;
- claim/recovery;
- return allocation;
- participant exit financial reconciliation;
- Stage;
- QA/Testing gate completion;
- Release Approval;
- Production;
- Direct Lending;
- real-money use.

## Stage Boundary

Decision 0023 remains in force.

Sprint 02 may be implemented and reviewed while Stage is unavailable, but the resulting code only accumulates into the future Stage candidate.

## Definition-of-Done Gate

Sprint 02 Code must satisfy the Accepted Definition of Done and the Sprint 02 plan, including:

- OIDC negative/positive authentication tests;
- deny-by-default scope tests;
- cross-program denial;
- auditor read-only behavior;
- Program/Participation correctness;
- configurable Asset Type behavior without gold hard-coding;
- exact Asset Position quantity persistence;
- both `PARTICIPANT_OWNED` and `PROGRAM_ATTRIBUTED`;
- append-only audit behavior;
- no secret/raw restricted-content leakage;
- migrations/format/lint/type/tests/dependency scan/container build green;
- Code Review complete.

## Approval Effect

This decision is **Accepted** and authorizes Code only for the Sprint 02 scope defined above.
