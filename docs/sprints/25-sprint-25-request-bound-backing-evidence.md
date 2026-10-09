# Sprint 25 — Request-bound Backing Evidence Foundation

- **Status:** Code / review pending exact-head green CI
- **Date:** 2026-10-09
- **Authorization:** Decision 0052 (technical evidence scope only)
- **Base:** Sprint 24 PR #27, Draft/Open

## Deliverables

1. One-statement typed request → episode → provider/product → multi-asset
   valuation-source projection.
2. Reuse existing canonical source inventory assembly; keep one source of truth.
3. Explicit fail-closed request state/scope/captured-product/version checks.
4. Exact facts/deterministic evidence fingerprint without financial judgment.
5. Real PostgreSQL integration regressions, full CI and technical Code Review.

## Not In Scope

No authenticated HTTP endpoint, Stage, production policy, risk/valuation
qualification, capacity, backing selection, locking, reservation, guarantee
transition, ledger, provider integration or use of synthetic evidence in runtime.

## Remaining Next Gate

BL-020 reservation Code Authorization still requires signed-off executable
allocation/hold and expiry policies, risk snapshot freshness/qualification
and atomic persistence/maker-checker/rollback lineage. Sprint 25 does not
close any of these business-policy gaps.
