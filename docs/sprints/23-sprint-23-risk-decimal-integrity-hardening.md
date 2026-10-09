# Sprint 23 — Portfolio Risk Decimal Integrity Hardening

- **Status:** Code + Technical Code Review Complete / Merge Pending Explicit Approval
- **Date:** 2026-10-09
- **Authorization:** Decision 0050, technical numeric-integrity correction
- **Base:** Sprint 22 Draft PR #25

## Deliverables

1. Fix positive-exponent integer precision check in Portfolio Risk.
2. Apply the same numeric storage-bound rules to versioned risk-policy decimals.
3. Preserve exact reserve/exposure arithmetic at NUMERIC(38,18) boundaries.
4. Add deterministic regression tests for valid/invalid boundary values.
5. Verify full CI then record scoped Code Review.

## Non-Goals

No new financial rule, threshold, risk state, reserve evaluator, coverage
policy, guarantee reservation, API endpoint, database migration, provider,
Frontend, Stage, QA, Production or merge.

## Unresolved Contracts

BL-020 needs approved asset allocation selection/locking semantics, reservation
expiry derivation, and a clearly versioned risk snapshot freshness/qualification
rule bound to the exact reservation inputs. Sprint 23 does not invent these.
BL-033 still needs governed production reserve requirement, eligibility,
coverage and draw/replenishment policies.

## CI / Review Handoff

- Code HEAD: `bd9b081875018580f92d90a027765f3bd18051e9`
- Code CI #409: SUCCESS (Secret Scan + Quality, including tests and container build).
- Code Review record: [23-sprint-23-code-review.md](./23-sprint-23-code-review.md).
- PR #26 must stay Draft/Open; merging or promotion requires explicit approval.
