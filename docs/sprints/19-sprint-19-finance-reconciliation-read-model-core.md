# Sprint 19 — Finance / Reconciliation Read Model Core

- **Status:** Code + Code Review Complete / Merge Pending Explicit Approval
- **Date:** 2026-10-08
- **Stage:** Sprint
- **Scope:** backend-first / BL-046 backend core
- **Base Dependency:** Sprint 18 branch for current stacked repository state; functional dependencies are BL-030, BL-042, BL-043
- **Branch Strategy:** stacked on `sprint-18-recovery-verification-core`
- **Traceability:** Technical 07 §§27-28; Technical 13 §§18,21; BL-046
- **Code Authorization:** GRANTED BY DECISION 0045

## Sprint Goal

Complete the backend read-model contract required by BL-046 without creating a parallel finance or reconciliation API.

The existing canonical surfaces remain:

- `GET /api/v1/reconciliation/cases`;
- `GET /api/v1/reconciliation/cases/{id}`;
- `GET /api/v1/finance/journals`;
- `GET /api/v1/finance/journals/{id}`;
- existing governed reversal and reconciliation-resolution commands.

Sprint 19 only fills missing operational read context needed by finance/reconciliation operations.

## Authorized Additive Read Fields

Reconciliation list/detail responses may add deterministic read-only fields derived from authoritative persisted state:

- `age_seconds` from `first_detected_at`;
- `last_observed_age_seconds` from `last_observed_at`;
- `active_block_count` from active `ReconciliationBlock` rows for the case;
- exact run timing/context already persisted on `ReconciliationRun`, including run status and cutoffs where useful to expose;
- provider context already represented by `external_provider_id`.

No freshness category, threshold, SLA, severity remapping, or health score may be invented.

## Read Model Freshness Semantics

This Sprint follows Technical 13 §18 without inventing projection infrastructure.

The reconciliation API is a direct database read over authoritative reconciliation state, not a separate asynchronously rebuilt projection.

Therefore:

- case `version` remains the source aggregate version;
- `first_detected_at` and `last_observed_at` remain authoritative timestamps;
- age fields are deterministic elapsed-time derivations;
- no fake `projection_version` or fake lag metric is created;
- no read response may claim real-time external provider freshness beyond persisted reconciliation evidence.

## Reconciliation Queue

Existing filters remain canonical:

- type;
- status;
- materiality;
- provider;
- minimum age.

Sprint 19 may strengthen tests proving those filters and the additive age/block fields.

No new reconciliation state transition is authorized.

## Finance Journal Read Model

Existing journal list/detail APIs remain canonical and read-mostly.

Sprint 19 may harden tests proving:

- FINANCE_RECONCILIATION and AUDITOR can inspect authorized journals;
- AUDITOR remains unable to reverse;
- no arbitrary journal create/update endpoint exists;
- reversal continues through the existing maker-checker command only.

No duplicate finance workspace endpoint is authorized unless an accepted contract later requires it.

## Security / Scope

Read authorization remains exactly the existing provider/global reconciliation scope and legal-entity journal scope.

The Sprint must not broaden access across providers, legal entities, participants, or unrelated records.

No provider secret, credential, restricted payload, or unrelated participant data may be exposed.

## Explicit Non-Goals

No UI/Figma/frontend; no new finance mutation; no generic admin override; no new reconciliation mutation; no new ledger engine; no new projection store; no freshness threshold; no SLA; no incident severity formula; no BL-020/023/026; no Stage/QA/Release/Production.

## Delivery Boundary

Sprint 19 ends at backend Code + Code Review for the BL-046 read-model core.

This does not claim the UI workspace portion of BL-046 complete.

Any PR remains Draft/Open and must not merge without explicit user instruction.
