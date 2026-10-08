# Decision 0040 — Sprint 14 Reconciliation Engine Core; Code Authorization

- **Status:** Accepted
- **Date:** 2026-10-08
- **Scope:** Sprint 14 / backend reconciliation control / Code Authorization
- **Depends on:** Decision 0039; BL-024; BL-025; BL-030; BL-041; Technical 04, 06, 07, 08, 09, 10, 11
- **Authorizes:** BL-042 Core + lender reconciliation vertical slice only

## Decision

Accept Sprint 14 and authorize Code for the governed Reconciliation Engine Core and the first real source-backed lender reconciliation path.

The Sprint may implement:

- versioned Reconciliation Policy resolution through the existing Pilot Policy Pack;
- reconciliation run/case/observation persistence;
- append-only reconciliation observations;
- deterministic run idempotency for the same source snapshot + exact rule version;
- lender snapshot comparison against ExternalLoanMirror and linked GuaranteeCase;
- reconciliation run and case read APIs;
- provider-scoped execution/read authorization;
- audit and transactional outbox evidence.

## Lender Comparison

The lender path may fetch authoritative snapshots only through the BL-024 Lender Adapter boundary.

The comparison must cover the authoritative fields available from the normalized snapshot contract and must support detection of:

- exact match;
- missing external record;
- missing internal record;
- duplicate external record;
- original/outstanding amount mismatch;
- currency/state mismatch;
- stale source;
- linked guarantee / external-loan principal invariant mismatch.

Repayment/disbursement/delinquency/settlement comparison may be added only from normalized authoritative fields, never inferred from UI or provider silence.

## Rule Governance

No freshness duration, tolerance, numeric materiality threshold, cadence, or safe default may be hard-coded.

The exact Reconciliation Policy version must be pinned for every run.

Missing policy, invalid policy, missing adapter, unavailable provider, or insufficient authoritative evidence fails closed.

## Generic Core Boundary

Core persistence/type vocabulary may represent lender, guarantee issuer, custody/asset, settlement, collateral-registry, and internal ledger/sub-ledger reconciliation.

Sprint 14 does not invent missing authoritative adapters or provider contracts. A domain with no real/accepted source integration remains unavailable rather than receiving fabricated data.

## BL-043 Boundary

Sprint 14 does not implement:

- propose/approve resolution;
- DISPUTED → RESOLVED workflow;
- reconciliation_blocks projection;
- maker-checker resolution;
- command blocking/clearing.

Those remain BL-043.

## Explicitly Unauthorized

No BL-020, BL-021, BL-022, BL-023, BL-026, guarantee activation, BackingAllocation encumbrance, repayment financial effect, direct ledger mutation from reconciliation, provider credential fabrication, Stage claim, QA pass, Release Approval, Production, or real-money behavior.

## Stage Boundary

Decision 0033 remains active. Stage is available but is not automatically executed by this Sprint because the current strategy is backend-first.

## Approval Effect

Code is authorized only inside this Sprint 14 boundary. The PR must remain Draft/Open through Code Review and must not be merged without explicit user instruction.
