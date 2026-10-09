# Sprint 28 — Governed Guarantee Operations Query Foundation

- **Date:** 2026-10-09
- **Status:** Code + Technical Code Review COMPLETE / Merge Pending Explicit Approval
- **Scope:** Accepted Technical 07 §19 and Technical 11 scoped-read contract
- **Base:** Sprint 27 Draft PR #30 (green CI #433)
- **Code:** Backend only; no Figma, Stage, QA, Release, or Production

## Outputs

1. Bounded `GET /api/v1/guarantees?program_id=<uuid>` with
   active human Program/GLOBAL read grant, stable UUID keyset cursor,
   optional state filter, maximum 100 records and exact persisted decimals.
   The SQL query itself binds the requested Program, not only an API check.
2. `GET /api/v1/guarantees/{id}/workspace` exposes a partial,
   **observation-only** operational context: the persisted case, program,
   participant ID, episode, captured provider/product version, and
   independently recorded external loan if one exists. For REQUESTED
   only it reuses existing authorized, fail-closed multi-asset evidence
   read; non-REQUESTED data never inherits an unqualified source view.
3. Null source sections and `false` availability fields mean the
   corresponding financial contract has not been implemented; these are
   **not** real-world absence or negative eligibility judgments.
4. Provider/product/mirror/Program lineage inconsistencies fail closed.
   Authorization scope is re-bound to the SQL read and never client-supplied
   as a workspace override.
5. Integration tests verify paging, role scope, negative cross-program
   access, request-evidence lineage, unsupported-state observation and
   mismatch refusal. No business-state, journal, decision or provider action.

## Not Authorized / Remaining Backend Work

This does **not** complete BL-045 Guarantee Operations Workspace.
No returned actions/eligibility, real allocation listing, legal claim,
reserve/risk activation, approval, repayment or recovery summary.
BL-020 reservation is still Code-blocked by explicit multi-asset capacity,
allocation/holds/expiry/locking, legal and Risk Snapshot business rules.
Other financial dependencies remain unchanged; no assumptions/fabricated
source observations or real-money behavior.

## Final Verification

- Exact reviewed code HEAD: `cf88bff62b332eb3cb8d36668c3e0d2c4648cc9b`
- Full code CI #438: SUCCESS (311 tests, Quality and Secret Scan)
- [Technical Code Review](./28-sprint-28-code-review.md)
- PR #31 remains Draft/Open; no Merge, Stage, QA, Release, Production or Figma.
