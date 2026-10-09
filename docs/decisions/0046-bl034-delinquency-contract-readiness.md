# Decision 0046 — BL-034 Delinquency Processing Contract Readiness

- **Status:** Accepted / Code Blocked
- **Date:** 2026-10-09
- **Scope:** BL-034 Delinquency Processing readiness review
- **Traceability:** Technical 03 — ACTIVE → DELINQUENT; Technical 08 §15; BL-034
- **Code Authorization:** NOT GRANTED

## Decision

BL-034 is not Code-ready for the GuaranteeCase delinquency transition.

Badban already has a lender-authoritative inbound event path for `LOAN_DELINQUENT`:

- the lender adapter normalizes `LOAN_DELINQUENT`;
- normalized delinquency requires an explicit `delinquency_state`;
- inbox ingestion is provider-scoped and idempotent;
- ExternalLoanEvent preserves lender event history;
- ExternalLoanMirror may reflect lender-authoritative `DELINQUENT` state;
- duplicate/stale provider events remain governed by existing event ordering/idempotency rules.

This existing integration foundation must not be rebuilt in BL-034.

## Blocking Contract

Technical 03 requires GuaranteeCase `ACTIVE → DELINQUENT` only when:

1. lender-authoritative delinquency evidence exists; and
2. the delinquency threshold defined by the **captured CreditProductVersion** is satisfied.

The first condition is implemented.

The second condition is not executable because `CreditProductVersion.delinquency_definition` is currently persisted as opaque JSON with no accepted evaluator schema or deterministic interpretation contract.

Therefore Badban must fail closed and must not transition GuaranteeCase to `DELINQUENT` merely because a lender event says the external loan is delinquent.

## Missing Contract That Must Be Defined Before Code

A future Business/Technical decision must define, without ambiguity:

- the allowed schema/version for `delinquency_definition`;
- which lender-authoritative fields are eligible inputs to the delinquency evaluator;
- whether delinquency eligibility is based on provider state, elapsed duration, payment status, another explicit field, or a defined combination;
- exact missing-data semantics;
- exact timezone/time-boundary semantics if time is part of the rule;
- whether evaluation is event-time or processing-time based;
- how product-version lineage is pinned to the GuaranteeCase;
- how corrections to lender evidence affect an already evaluated delinquency condition;
- stable fail-closed errors for missing/unsupported/invalid delinquency definitions;
- whether a provider-reported delinquency may remain mirror-only when the product threshold is not satisfied.

No numeric threshold, grace period, day count, status mapping, or default rule is authorized by this decision.

## Required Invariants For Future BL-034 Code

When the missing contract is later accepted:

- evaluation must use the exact captured CreditProductVersion, never the latest current product version;
- lender evidence must remain authoritative and immutable/history-preserving;
- duplicate inbound events must not duplicate effects;
- a stale/history-only lender event must not trigger a new GuaranteeCase transition;
- GuaranteeCase transition must be idempotent and concurrency-safe;
- no claim is auto-submitted or auto-paid;
- no journal posting is created merely because delinquency is observed;
- reconciliation blocks and operational stop controls remain independently authoritative;
- a missing/invalid delinquency definition must fail closed.

## Explicit Non-Goals

This decision does not:

- invent a delinquency threshold;
- define a product delinquency JSON schema;
- map arbitrary provider status strings to Badban eligibility;
- authorize GuaranteeCase mutation;
- authorize claim creation/settlement;
- authorize BL-035/036;
- authorize UI/Figma/frontend;
- authorize Stage/QA/Release/Production.

## Readiness Result

`BL-034 Code = BLOCKED`

The next safe action is a Business/Technical contract for executable `delinquency_definition` semantics.

Until that contract exists, Badban may continue to preserve lender-authoritative delinquency evidence and mirror state, but must not infer the GuaranteeCase delinquency transition.
