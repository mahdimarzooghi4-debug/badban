# Sprint 21 — Guarantee Reserve Metrics Snapshot

- **Status:** Accepted / Code Authorized
- **Date:** 2026-10-09
- **Stage:** Sprint
- **Scope:** BL-033 prerequisite / reserve metrics producer
- **Base Dependency:** Sprint 20
- **Branch Strategy:** stacked on `sprint-20-delinquency-evaluator-foundation`
- **Traceability:** Decision 0010 §§2-4,11-13; Technical 05 §§3-6,18-19; BL-033
- **Code Authorization:** GRANTED BY DECISION 0048

## Sprint Goal

Create an append-only, auditable reserve-metrics snapshot from Badban's posted Journal truth.

The snapshot keeps actual reserve cash control and designated reserve balance separate.

## Canonical Accounts

Only the accepted product account taxonomy is used:

- `1020.GUARANTEE_RESERVE_CASH_CONTROL` — debit-normal controlled reserve cash;
- `2040.GUARANTEE_RESERVE_DESIGNATED_BALANCE` — credit-normal reserve-purpose balance.

No AssetPosition, participant collateral, 9000 memorandum balance, provider mirror, or unrelated cash account is counted.

## Snapshot Semantics

For one legal entity and one currency:

`reserve_cash_control_balance = SUM(debit - credit)` on account 1020.

`reserve_designated_balance = SUM(credit - debit)` on account 2040.

Only postings whose JournalEntry is `POSTED` are included.

The snapshot preserves source Journal/Postings lineage and a deterministic source fingerprint.

## Important Non-Combination Rule

Sprint 21 must **not** derive:

- eligible available guarantee reserve;
- reserve coverage ratio;
- required reserve;
- target/warning/hard-minimum state;
- reserve sufficiency;
- draw authority;
- replenishment authority.

Those require versioned reserve-eligibility / risk policy semantics.

The two balances must remain separately visible.

## Persistence

A `GuaranteeReserveMetricsSnapshot` may be added as append-only evidence/read state.

It may persist:

- legal entity;
- currency;
- cash-control balance;
- designated balance;
- source journal IDs;
- source posting IDs;
- source fingerprint;
- algorithm code/version;
- actor/correlation;
- evaluated timestamp.

It must not duplicate or mutate financial truth.

## Idempotency

If the exact legal-entity/currency source posting set is unchanged, recomputation returns the existing snapshot for the same fingerprint.

Any new or reversed POSTED reserve posting changes source lineage/fingerprint and produces a new snapshot.

## Authorization

Snapshot creation: human `FINANCE_RECONCILIATION` or `RISK`, scoped to the legal entity (global grants may authorize via existing rules).

Snapshot read: `FINANCE_RECONCILIATION`, `RISK`, or `AUDITOR` under the same legal-entity scope.

AUDITOR remains read-only.

## Explicit Non-Goals

No reserve draw/replenishment command; no cash settlement integration; no reserve-eligibility evaluator; no reserve requirement calculator; no coverage ratio; no Production percentages; no BL-035/036; no UI/Figma/frontend; no Stage/QA/Release/Production.

## Delivery Boundary

Sprint 21 ends at Code + Code Review for the reserve-metrics snapshot producer only.

BL-033 remains incomplete until reserve eligibility and governed draw/replenishment behavior are separately contracted.
