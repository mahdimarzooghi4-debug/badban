# Decision 0045 — Sprint 19 Finance / Reconciliation Read Model Core; Code Authorization

- **Status:** Accepted
- **Date:** 2026-10-08
- **Scope:** Sprint 19 / BL-046 backend read-model core / Code Authorization
- **Depends on:** BL-030; BL-042; BL-043; Technical 07 §§27-28; Technical 13 §§18,21
- **Authorizes:** additive read-model completion on existing finance/reconciliation APIs only

## Decision

Authorize Code to complete the backend finance/reconciliation operational read model using the existing canonical APIs and persistence truth.

No parallel workspace API, projection subsystem, UI, or new mutation path is authorized.

## Existing Canonical Surfaces

Sprint 19 must build on:

- `GET /api/v1/reconciliation/cases`;
- `GET /api/v1/reconciliation/cases/{id}`;
- `GET /api/v1/finance/journals`;
- `GET /api/v1/finance/journals/{id}`;
- existing governed journal reversal;
- existing reconciliation proposal/approval/recheck commands.

## Reconciliation Read Fields

The list/detail response may expose deterministic operational fields derived only from persisted state:

- case age in seconds from `first_detected_at`;
- last-observed age in seconds from `last_observed_at`;
- active reconciliation block count for the case;
- persisted reconciliation run status/cutoff context where exposed additively;
- existing provider, materiality, status, version, and timestamps.

Elapsed-time values must be derived from a single request-time UTC timestamp so fields in one response remain internally coherent.

## No Invented Freshness Policy

Sprint 19 must not introduce:

- freshness buckets;
- warning/critical time thresholds;
- provider SLA values;
- health scores;
- materiality remapping;
- automatic escalation rules.

Persisted `STALE` remains the domain state when already produced by accepted reconciliation rules.

Age is information, not a new decision rule.

## Direct Read Model Semantics

The current reconciliation API reads authoritative persisted reconciliation state directly.

It must not claim an asynchronous projection version or projection lag that does not exist.

The existing case `version` is the authoritative aggregate version.

No new projection store is authorized.

## Queue Contract

The existing queue filters remain:

- type;
- status;
- materiality;
- provider;
- minimum age.

Tests must prove filters compose correctly and cannot broaden authorization scope.

## Block Context

Active-block context is read-only.

Exposing `active_block_count` must not clear, create, resolve, or otherwise mutate a `ReconciliationBlock`.

Block state remains owned by the existing reconciliation blocking/resolution bounded context.

## Journal Contract

Journal list/detail remains read-mostly and legal-entity scoped.

Sprint 19 must prove:

- authorized finance/auditor reads continue to work;
- AUDITOR cannot reverse;
- no arbitrary journal create/update API exists;
- reversal remains maker-checker governed;
- no balance or posting value is derived from a UI/read model.

## Authorization

Reconciliation reads retain the existing provider/global authorization behavior.

Journal reads retain existing legal-entity authorization behavior.

No cross-provider or cross-legal-entity broadening is authorized.

No unrelated participant data, provider credentials, raw secrets, or restricted provider payload may be exposed.

## Explicit Non-Goals

No UI/Figma/frontend; no new finance mutation; no new reconciliation mutation; no generic admin override; no provider call; no ledger redesign; no projection database; no BL-020/023/026; no Stage/QA/Release/Production.

## Approval Effect

Code is authorized only for the additive, read-only BL-046 backend core described above.

The Sprint may close the backend read-model portion of BL-046, but must not claim the UI workspace portion complete.

Any PR remains Draft/Open and must not merge without explicit user authorization.
