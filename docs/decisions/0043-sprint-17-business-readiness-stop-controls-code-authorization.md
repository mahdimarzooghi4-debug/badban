# Decision 0043 — Sprint 17 Business Readiness and Stop Controls Core; Code Authorization

- **Status:** Accepted
- **Date:** 2026-10-08
- **Scope:** Sprint 17 / BL-049 Core / Code Authorization
- **Depends on:** BL-005; BL-032; Sprint 14 BL-042; Sprint 16 BL-043; Technical 13 §§7,29,35-36
- **Authorizes:** BL-049 backend core only

## Decision

Authorize a separate Business Readiness control plane plus explicit operational stop controls. Sprint 17 is stacked on Sprint 16 to preserve the linear Alembic migration chain; this does not authorize merging Sprint 16 or Sprint 17.

## Canonical Stop Types

Only:

- `STOP_NEW_GUARANTEE_RESERVATIONS`
- `STOP_GUARANTEE_ACTIVATION`
- `SUSPEND_PROVIDER_FOR_NEW_ACTIONS`
- `SUSPEND_ASSET_TYPE_FOR_NEW_ACTIONS`
- `STOP_CLAIM_SETTLEMENT`
- `STOP_COLLATERAL_RELEASE`

No additional stop type is authorized.

## Scope Contract

Allowed scope pairs are exact:

- reservation stop → GLOBAL;
- guarantee activation stop → GLOBAL;
- provider suspension → PROVIDER;
- Asset Type suspension → ASSET_TYPE;
- claim settlement stop → GLOBAL;
- collateral release stop → GLOBAL.

A mismatched control/scope fails closed.

## Restrictive-Only Invariant

A stop control may refuse a new action. It must never rewrite or repair:

- GuaranteeCase;
- ExternalLoanMirror;
- BackingAllocation;
- CreditProvider lifecycle;
- AssetType lifecycle;
- Journal;
- claim/recovery state;
- reconciliation history;
- any existing financial obligation.

Provider/Asset Type suspension here is an operational overlay only.

## Activation / Clearing

Activation and clearing must be explicit, human-authorized, audited, idempotent, concurrency-safe, and versioned/traceable.

Clearing a stop control does not imply Business Readiness if any other required authoritative condition remains unsafe or unavailable.

## Business Readiness

Business Readiness is separate from liveness and infrastructure readiness.

Only authoritative implemented signals may contribute. The core may use:

- active stop controls;
- exact-scope active Pilot Policy Pack;
- exact-scope latest PortfolioRiskSnapshot;
- active reconciliation blocks;
- STALE reconciliation cases;
- explicitly scoped provider/Asset Type lifecycle state.

No numeric threshold is introduced.

Missing required policy/risk/reconciliation evidence must not silently become READY. No implicit GREEN. No provider silence is success.

## Readiness Result

The backend may expose `READY` or `NOT_READY` plus explicit machine-readable reasons and source references. This read/control result does not mutate domain aggregates.

## Authorization

Stop-control mutation is limited to existing human operational/governance roles. Auditors are read-only. Existing RBAC/audit primitives must be reused; no parallel identity/approval system is authorized.

## Command Gate

Reusable stop/readiness checks may be exposed for future protected commands, but this decision does not authorize implementation of BL-020, BL-023, BL-026, claim settlement, or collateral release itself.

## Explicit Non-Goals

No BL-020, BL-023, BL-026, BL-033, BL-034, BL-035/036, provider credentials, new readiness thresholds, UI/Figma/frontend, Stage/QA/Release/Production, or real-money behavior.

## Approval Effect

Code is authorized only for the Sprint 17 BL-049 core above. Any PR remains Draft/Open through Code Review and must not merge ahead of prerequisites or without explicit user instruction.
