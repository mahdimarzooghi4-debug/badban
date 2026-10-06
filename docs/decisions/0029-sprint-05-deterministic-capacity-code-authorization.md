# Decision 0029 — Sprint 05 Deterministic Guarantee Capacity Calculator; Code Authorization

- **Status:** Accepted
- **Date:** 2026-10-06
- **Scope:** Sprint 05 / Code Authorization / Bounded External-Lender Pilot
- **Depends on:** Decision 0023; Sprint 04 Code Review Complete; Decision 0008; Technical 06

## Decision

Accept Sprint 05 and authorize Code only for:

- **BL-015 — Deterministic Guarantee Capacity Calculator**

## Rationale

BL-015 dependencies are complete through Code Review:

- BL-011 in Sprint 02;
- BL-012 in Sprint 03;
- BL-014 in Sprint 04.

The next safe increment is the deterministic arithmetic core only. Read-model, portfolio-risk, provider/legal, reservation, guarantee, lending, and monetary side effects remain outside this authorization.

## Authorized Scope

Implementation may include:

- pure exact-Decimal capacity calculation types/functions;
- deterministic per-position gross, pledgeable, and backing calculations;
- deterministic aggregation of uncapped position backing;
- final available-capacity arithmetic using explicit capped gross backing, reservation, exposure, and hold inputs;
- explicit validation of non-negative values and `[0,1]` fractions;
- existing immutable valuation freshness/evidence integration;
- explicit algorithm-version metadata;
- exact Policy Pack/component version evidence;
- integration with existing DecisionSnapshot service;
- tests and documentation required for BL-015.

## Rounding and Policy-Value Boundary

This decision does not approve any production numeric policy values or production rounding mode.

Sprint 05 must:

- use exact Decimal arithmetic;
- perform no implicit quantization/rounding;
- never use binary floating point for authoritative capacity;
- never invent Advance Rate, pledgeable fraction, FX, cap, stale window, reserve threshold, or other policy values;
- require explicit upstream values/evidence where needed.

Any later monetary quantization policy requires an explicit accepted contract.

## Portfolio/Cap Boundary

BL-032 remains unauthorized.

Sprint 05 may accept an explicit `capped_gross_backing_capacity` as an input to final availability arithmetic, but must not invent or implement concentration/portfolio cap logic.

Missing cap/control data must fail closed rather than silently treating uncapped gross backing as capped capacity.

## Hard Invariants

1. Same exact inputs + same policy versions + same algorithm version produce the same result.
2. No implicit latest policy lookup.
3. No guessed valuation, FX, fraction, cap, or policy value.
4. Stale/expired valuation creates no new capacity.
5. Exact Decimal only; no binary float path.
6. Calculation alone creates no reservation, BackingAllocation, guarantee exposure, ledger posting, provider action, or legal effect.
7. Algorithm version remains separate from policy version.
8. Material calculation evidence is capturable in immutable DecisionSnapshot.
9. No portfolio-risk decision is implemented under BL-015.
10. No real-money behavior is authorized.

## Explicitly Unauthorized

This decision does not authorize:

- BL-016 Guarantee Capacity Read Model;
- BL-032 Portfolio Risk Snapshot/Gate;
- Provider/Product Registry;
- Legal Entity Authorization Registry;
- guarantee request/reservation/issuance/activation;
- lender or guarantee-provider integration;
- BackingAllocation reservation;
- claims/recovery;
- return allocation;
- participant exit financial reconciliation;
- Direct Lending;
- production policy numeric values;
- production rounding policy;
- Stage;
- QA/Testing gate completion;
- Release Approval;
- Production;
- real-money use.

## Definition-of-Done Gate

Sprint 05 must satisfy the Accepted Sprint 05 plan, including:

- exact-decimal formula tests;
- stale/expired valuation tests;
- missing required input fail-closed tests;
- version/reproducibility tests;
- DecisionSnapshot evidence tests;
- no-side-effect tests;
- full CI gates;
- Code Review complete.

## Stage Boundary

Decision 0023 remains in force.

Sprint 05 may be implemented and reviewed while Stage is unavailable, but its reviewed output only accumulates into the future Stage candidate.

## Approval Effect

This decision is Accepted.

Code is authorized only for BL-015 within the boundaries above.
