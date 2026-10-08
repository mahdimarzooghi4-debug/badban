# Sprint 17 — Business Readiness and Stop Controls Core

- **Status:** Code + Code Review Complete / Merge Pending Explicit Approval
- **Date:** 2026-10-08
- **Stage:** Sprint
- **Scope:** backend-first / BL-049 core
- **Base Dependency:** Sprint 16 BL-043 Code + Code Review complete on PR #19
- **Branch Strategy:** stacked on `sprint-16-reconciliation-blocks-resolution` to preserve the linear migration chain
- **Traceability:** Technical 13 §§7, 29, 35-36
- **Code Authorization:** GRANTED BY DECISION 0043

## Sprint Goal

Implement explicit restrictive operational stop controls and a separate Business Readiness view without inventing thresholds, mutating existing obligations, or treating infrastructure health as business correctness.

## Canonical Stop Controls

Only:

- `STOP_NEW_GUARANTEE_RESERVATIONS`
- `STOP_GUARANTEE_ACTIVATION`
- `SUSPEND_PROVIDER_FOR_NEW_ACTIONS`
- `SUSPEND_ASSET_TYPE_FOR_NEW_ACTIONS`
- `STOP_CLAIM_SETTLEMENT`
- `STOP_COLLATERAL_RELEASE`

Scope is fixed by control type: global for reservation/activation/claim-settlement/collateral-release; provider for provider suspension; asset-type for Asset Type suspension.

## Core Rules

- restrictive only;
- no rewrite of existing obligations or lifecycle history;
- provider/asset suspension is an overlay and does not mutate provider/asset lifecycle;
- activation and clearing are explicit, idempotent, concurrency-safe and audited;
- auditors are read-only;
- Business Readiness is distinct from `/health/live` and `/health/ready`;
- no numeric thresholds are introduced;
- no missing required signal becomes READY;
- no implicit GREEN;
- no provider silence becomes success.

## Business Readiness Inputs

Use only authoritative implemented signals, including as applicable:

- active stop controls;
- active Pilot Policy Pack for the exact supplied policy scope;
- latest PortfolioRiskSnapshot for that exact scope;
- active reconciliation blocks and STALE reconciliation cases;
- provider/asset lifecycle state for explicitly scoped evaluation.

No legal-role mapping or provider-health policy is invented if the applicable authoritative contract cannot be resolved.

## API/Core Boundary

Authorized backend surfaces may include:

- activate stop control;
- clear stop control;
- list/read current controls;
- evaluate Business Readiness;
- deterministic reusable stop-control gate.

Sprint 17 does not implement the protected reservation, activation, claim-settlement, or collateral-release domain command itself.

## Non-Goals

No BL-020, BL-023, BL-026, BL-033, BL-034, BL-035/036, collateral release workflow, UI/Figma/frontend, Stage/QA/Release/Production, provider credentials, or real-money behavior.

## Test Contract

Cover canonical scope validation, fail-closed invalid scope/type, idempotent/race-safe activation and clear, matching vs unrelated gate behavior, lifecycle non-mutation, readiness separation from infrastructure health, active stop → NOT_READY, missing policy/risk → NOT_READY, audit, and auditor read-only behavior.

## Delivery Boundary

Sprint ends at Code + Code Review. PR remains Draft/Open and stacked on Sprint 16; it must not merge ahead of prerequisites or without explicit user instruction.
