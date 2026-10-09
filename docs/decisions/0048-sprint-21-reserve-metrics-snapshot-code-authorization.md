# Decision 0048 — Sprint 21 Reserve Metrics Snapshot; Code Authorization

- **Status:** Accepted
- **Date:** 2026-10-09
- **Scope:** Sprint 21 / BL-033 prerequisite / Code Authorization
- **Depends on:** Decision 0010; BL-030; BL-031; Technical 05
- **Authorizes:** append-only posted-Journal reserve metrics snapshots only

## Decision

Authorize Code for a deterministic reserve-metrics producer based exclusively on Badban's posted monetary Journal.

This is a metrics/evidence producer, not a reserve-policy decision engine.

## Financial Truth

The producer must derive balances only from `POSTED` JournalEntry/JournalPosting rows.

Account semantics are fixed by Technical 05:

- `1020.GUARANTEE_RESERVE_CASH_CONTROL` is debit-normal;
- `2040.GUARANTEE_RESERVE_DESIGNATED_BALANCE` is credit-normal.

Therefore:

- cash control = debit minus credit;
- designated balance = credit minus debit.

## Separation Invariant

The balances must remain separate.

Code must not use `min()`, `max()`, addition, subtraction, or another composition rule to label an amount as `reserve_available` or `eligible reserve`.

Decision 0010 requires a separate reserve-eligibility policy before coverage can be determined.

## Ownership Boundary

Participant-owned backing assets are not general guarantee reserve.

The metrics producer must not query AssetPosition or infer reserve from custody/encumbrance records.

Only canonical reserve Journal account codes enter the snapshot.

## Lineage

Each snapshot binds to exact:

- legal entity;
- currency;
- source POSTED Journal IDs;
- source reserve Posting IDs;
- deterministic source fingerprint;
- algorithm code/version;
- actor;
- correlation;
- evaluation time.

The record is append-only.

## Idempotency

Same scope + same source fingerprint returns the existing snapshot.

Changed POSTED reserve source state creates a new snapshot.

## Authorization

Creation is permitted only to human `FINANCE_RECONCILIATION` or `RISK` actors authorized for the legal entity.

Read is permitted to `FINANCE_RECONCILIATION`, `RISK`, and `AUDITOR` for the authorized legal entity.

## Risk Engine Boundary

Sprint 21 does not automatically feed a value into `RiskEvaluationInputs.reserve_available`.

It may provide a stable `reserve_metrics_reference` for a later accepted reserve-eligibility integration.

Until that integration exists, Risk evaluation callers must not infer reserve availability from these two balances.

## Explicit Non-Goals

No reserve requirement formula; no reserve coverage ratio; no numeric risk threshold; no draw/replenishment mutation; no settlement-provider evidence handling; no claim payment; no accounting template changes; no UI; no Stage/QA/Release/Production.

## Approval Effect

Code is authorized only for the Sprint 21 reserve metrics snapshot producer.

BL-033 remains partially incomplete after this Sprint.
