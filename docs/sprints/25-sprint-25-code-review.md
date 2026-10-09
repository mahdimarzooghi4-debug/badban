# Sprint 25 — Technical Code Review Record

- **Status:** Technical Code Review COMPLETE, not independent Human Release Approval
- **Date:** 2026-10-09
- **Scope:** request-bound backing source evidence, read-only BL-020 prerequisite
- **PR:** #28, Draft/Open, stacked on PR #27
- **Reviewed exact code HEAD:** `e38c02f40d2f03a240635aceb2f024eb5df534ea`
- **Code CI #418:** SUCCESS (Secret Scan + Quality)

## Reviewed Surface

- `src/badban/application/request_bound_backing_evidence.py`
- shared `src/badban/application/backing_source_inventory.py` assembly refactor
- `tests/test_sprint25_request_bound_evidence.py`
- Decision 0052 and BL-020 Contract Dossier §5

## Verified Technical Invariants

1. A single SQL statement retrieves one persisted GuaranteeCase, episode,
   captured provider/product and every persisted episode asset and valuation
   observation. No between-query optimistic assumption is introduced here.
2. Only REQUESTED case evidence is projected. Reserved, issued, exposure,
   expiry or risk-snapshot residue on a REQUESTED case is rejected rather
   than silently treated as readiness.
3. Episode and requested program must match; captured credit product must
   belong to the case's provider; guarantee mode must agree; aggregate and
   product version numbers must be valid.
4. Shared typed source-inventory assembly preserves multi-asset ownership,
   legal owner/custodian, asset-type and aggregate version, unit/quantity,
   all historical valuations, and absent valuations without inferring them.
5. Product/provider lifecycle status is **observed**, not decided: even DRAFT
   facts may be displayed as a DRAFT state in this internal evidence view
   and never interpreted as eligible.
6. Stable fingerprint reflects the serialized observed source facts only.
   It is not signed, independently attested, transactionally locked, or
   sufficient for an accepted risk/valuation/eligibility/reservation decision.
7. No HTTP entrypoint, authorization relaxation, provider integration,
   mutation, journal posting, decision snapshot, outbox event, Stage or Release.

## PostgreSQL Test Evidence

Five added integration tests verify:

- request → actual provider/product → two source positions and a real
  valuation, with deterministic repeat and no financial side effects;
- missing guarantee and cross-program isolation;
- refusal to inspect a transitioned/non-REQUESTED guarantee;
- contradictory captured product/provider binding, using real FK-valid
  distinct provider records;
- fingerprint change when a persisted backing source changes.

The pre-existing Sprint 24 inventory regressions remain in the full suite.

## CI Failures Fixed Before Review

- #415 Format failed for two layout differences; fixed at
  `f745440cd6f0bdf0b6021499ead2b2aadb093469`.
- #416 Lint failed for `collections.abc.Sequence` and sorted imports;
  fixed at `c7ea5d46b17bdafafea8d9499296168e2759c273`.
- #417 Type Check found a test fixture annotation `dict[str, object]` where
  UUID arguments were required; fixed at
  `e38c02f40d2f03a240635aceb2f024eb5df534ea`.
- #418 full CI passed, with no subsequent source code change.

## Remaining Gaps / Explicit Limits

This remains an **internal** read primitive. Before exposure to a user,
a future API must enforce actor, provider and Program role scope and
sensitive-field minimization. The single SQL view is a consistent
observation, not a concurrency control or accept/reject policy. Product
authorization, legally valid custody, valuation acceptance/freshness,
reserve/hold completeness, risk snapshot qualifications, allocation
selection and lock ordering, explicit expiry policy, and atomic transition
persistency still require approved executable contracts.

No financial rule/threshold or synthetic source is activated.
**BL-020 REQUESTED → RESERVED is still BLOCKED.**

## Gate

`Code = COMPLETE`

`Technical Code Review = COMPLETE`

`Merge / Stage / QA / Release / Production = NOT AUTHORIZED`
