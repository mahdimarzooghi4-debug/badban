# Decision 0028 — Sprint 04 Policy Lifecycle and Deterministic Resolution; Code Authorization

- **Status:** Accepted
- **Date:** 2026-10-06
- **Scope:** Sprint 04 / Code Authorization / Bounded External-Lender Pilot
- **Depends on:** Decision 0023; Decision 0027; Sprint 04 Plan

## Decision

Accept Sprint 04 and authorize Code only for:

- BL-013 — Policy Version and Policy Pack Lifecycle;
- BL-014 — PolicyResolver and DecisionSnapshot.

## Rationale

Sprint 03 completed the prerequisite foundations:

- BL-008 Maker-Checker / ApprovalRequest;
- BL-012 Immutable Valuation Observation;
- BL-030 Append-Only Journal Engine.

Sprint 04 deliberately stops at deterministic policy lifecycle/resolution so the policy runtime can be reviewed independently before it becomes an input to guarantee-capacity and portfolio-risk calculations.

## Authorized Scope

Implementation may include:

- versioned policy records;
- Pilot Policy Pack manifest with exact component version IDs;
- DRAFT → REVIEWED → APPROVED → ACTIVE → SUPERSEDED / RETIRED lifecycle;
- separate approval and activation commands;
- maker-checker integration where required by accepted impact rules;
- immutable ACTIVE policy content;
- canonical policy payload hashes;
- explicit scope/effective-time persistence;
- transactional exclusive-scope activation;
- atomic supersession of prior ACTIVE version where applicable;
- deterministic PolicyResolver;
- explicit component-version resolution;
- fail-closed missing/ambiguous/incompatible policy handling;
- append-only DecisionSnapshot persistence;
- historical replay from captured inputs/version IDs;
- migrations, audit/outbox evidence, tests, CI, and documentation required by BL-013/BL-014.

## Explicitly Unauthorized

Acceptance would not authorize:

- BL-015 Guarantee Capacity Calculator;
- BL-016 Guarantee Capacity Read Model;
- BL-032 Portfolio Risk Snapshot/Gate;
- production Pilot Policy numeric values;
- Provider/Product Registry;
- Legal Entity Authorization Registry;
- guarantee request/reservation/issuance;
- lender or guarantee-provider integration;
- external-loan mirror;
- claim/recovery;
- return allocation;
- participant exit financial reconciliation;
- Direct Lending;
- Stage;
- QA/Testing gate completion;
- Release Approval;
- Production;
- real-money use.

## Hard Invariants

Sprint 04 Code must preserve:

1. approval does not automatically activate;
2. only ACTIVE policy may authorize new pilot decisions;
3. ACTIVE content is immutable;
4. policy packs contain exact version IDs, never mutable latest pointers;
5. no material command uses implicit `getLatestPolicy()`;
6. missing policy fails closed;
7. ambiguous policy fails closed;
8. incompatible/missing component reference fails closed;
9. concurrent exclusive-scope activation cannot leave incompatible double-ACTIVE state;
10. policy version and algorithm version remain separate;
11. DecisionSnapshots are append-only;
12. historical replay uses captured inputs/version IDs and does not fetch fresh external facts;
13. later policy activation never rewrites historical DecisionSnapshots;
14. no guarantee-capacity, exposure, reservation, or monetary posting is created merely by policy resolution/snapshot creation.

## Definition-of-Done Gate

Sprint 04 must satisfy the Accepted Sprint 04 plan, including:

- lifecycle transition tests;
- separate approval/activation tests;
- maker-checker tests where required;
- ACTIVE immutability tests;
- concurrent activation conflict tests;
- exact version/hash tests;
- missing/ambiguous/incompatible PolicyResolver tests;
- no implicit latest-policy behavior;
- DecisionSnapshot immutability and replay tests;
- migrations and migration drift check;
- format/lint/type/security/dependency/container CI gates;
- Code Review complete.

## Stage Boundary

Decision 0023 remains in force.

Sprint 04 may be implemented and reviewed while Stage is unavailable, but its reviewed output will only accumulate into the future Stage candidate.

## Approval Effect

This decision is **Accepted**.

Sprint 04 Code is authorized only for BL-013 and BL-014 under the scope, non-goals, and invariants above.
