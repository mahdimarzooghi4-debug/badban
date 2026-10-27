# Sprint 52 — Service Program Lineage

## Goal

Make monthly pension and post-exit support records safely visible within the correct supporting-institution program and participant episode.

## Deliverables

- Add optional program and episode lineage to legacy-compatible benefit tables, with a composite database foreign key that enforces participant/program/episode consistency.
- Require program and episode IDs when creating new monthly-pension entitlements and post-exit cases.
- Restrict monthly-pension and post-exit funding sources to the selected program.
- Extend the support institution financial case with those exact-program and exact-episode benefit records.
- Show already-posted support return allocations by participant, program, and currency, separately from guarantee exposure and reported loan balances.
- Keep unlinked historical records out of the support institution view; do not guess or backfill their program assignment.

## Boundaries

- The service write routes remain governance controlled and maker-checker behavior is unchanged.
- Existing rows keep null lineage until verified data is supplied through an approved reconciliation process.
- Program return allocation totals are program-and-participant scoped, not episode scoped.
- No merge, Stage, release, or production operation is authorized.
