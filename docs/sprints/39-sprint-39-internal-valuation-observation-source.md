# Sprint 39 — Internal Valuation Observation Source

- **Status:** Implemented and merged to `main` via PR #45 on 2026-10-25; exact-head CI #508 and post-merge main CI #512 passed
- **Date:** 2026-10-25
- **Decision:** [0057 — Internal Valuation Observation Source](../decisions/0057-sprint-39-internal-valuation-observation-source.md)
- **Base:** Sprint 38 PR #42 (`sprint-38-internal-asset-inventory-source`)
- **Backlog:** BL-042 internal recorded-valuation source only

## Objective

Expose a verified program-scoped snapshot of valuation observations already
recorded in Badban while preserving their provenance labels and stored
freshness fields without promoting them to verified external facts.

## In scope

- Add a distinct `INTERNAL_VALUATION_OBSERVATION` snapshot and record contract.
- Read observations and their asset-position program lineage in one PostgreSQL
  statement with a statement-time cutoff.
- Preserve exact amounts, provenance labels, observation/receipt/validity times,
  recorded freshness status, and evidence references.
- Reject inconsistent scope, future observations, invalid numbers, and
  duplicates; missing rows remain unavailable.
- Add unit and PostgreSQL integration coverage.

## Explicitly out of scope

- Authenticating or calling an external valuation provider.
- Selecting a valuation, freshness threshold, tolerance, eligibility, or
  financial impact.
- Comparison/case creation, external adapters, BL-020, Stage, QA completion,
  Release, Production, or real-money behavior.

## Acceptance

- The internal source uses the existing registration and snapshot-verification
  boundary and exact program scope.
- Recorded freshness is reported without an automated freshness decision.
- PostgreSQL integration coverage confirms stored observation and program
  lineage are read without writes.
- Keep the PR Draft/Open/unmerged through exact-head CI and code review.

Implementation verification: four focused non-integration tests pass; Ruff,
Pyright, format, and diff checks pass. GitHub CI passed on exact head
`1f9fa977dccf5241c66c3d61e5327f2ad12d61ef` (run #506), including PostgreSQL
integration tests. The PR remains Draft/Open/unmerged pending code review.
