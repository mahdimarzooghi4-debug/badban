# Decision 0034 — Sprint 09 Portfolio Risk Snapshot and Gate; Code Authorization

- **Status:** Accepted
- **Date:** 2026-10-07
- **Scope:** Sprint 09 / Code Authorization / Bounded External-Lender Pilot
- **Depends on:** Decision 0010; Decision 0033; BL-013; BL-015; BL-030; Technical 02, 04, 06, 07, 08, 11

## Decision

Accept Sprint 09 and authorize Code only for:

- **BL-032 — Portfolio Risk Snapshot and Gate**

## Required Outcome

Implement a deterministic, immutable, policy-versioned PortfolioRiskSnapshot and the accepted risk read/evaluate API surface.

The implementation must bind each evaluation to one exact ACTIVE Pilot Policy Pack and exactly one referenced `RISK_APPETITE_POLICY` component, preserve evaluated inputs and policy lineage, and fail closed when the required policy or inputs are unavailable or invalid.

## No Invented Risk Values

No production risk percentage, portfolio limit, reserve target, warning threshold, hard minimum, concentration limit, stress assumption, recovery assumption, or default assumption is authorized by this decision.

All such values, when required by the evaluator, must come from the exact governed Risk Appetite Policy payload. Missing values are errors, not defaults.

## Risk Gate Semantics

The only authoritative risk states are:

- GREEN;
- AMBER;
- RED.

RED blocks new exposure growth.

No implicit GREEN, synthetic PASS, absent-snapshot PASS, or hard-coded safe state is permitted.

Existing obligations are not silently rewritten by a later risk state.

## Authorized API

Only:

    GET  /api/v1/risk/portfolio
    POST /api/v1/risk/portfolio/evaluate

POST is privileged/internal and participant access is forbidden. RISK may evaluate within authorized scope. AUDITOR is read-only.

## Persistence and Events

Portfolio risk snapshots are append-only.

A successful evaluation must atomically record snapshot + audit + `PortfolioRiskEvaluated` outbox event. `PortfolioRiskStateChanged` is emitted only when the new accepted snapshot differs from the previous snapshot for the same scope.

## BL-020 Boundary

BL-020 — Atomic Backing Reservation remains unauthorized in Sprint 09.

Sprint 09 only creates the authoritative risk gate prerequisite. BL-020 requires a later explicit Sprint/Code authorization and must capture a specific qualifying risk snapshot.

## Explicitly Unauthorized

BL-016, BL-020, BL-021, BL-031, BL-033, arbitrary production risk values, provider integration, real-money activity, Production deployment, and any bypass of policy/risk/legal/reconciliation controls remain unauthorized.

## Approval Effect

Code is authorized only for BL-032 within the Sprint 09 boundary.
