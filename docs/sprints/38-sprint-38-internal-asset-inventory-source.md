# Sprint 38 — Internal Asset Inventory Source

- **Status:** Implemented; exact-head CI passed; Draft PR pending code review
- **Date:** 2026-10-25
- **Decision:** [0056 — Internal Asset Inventory Source](../decisions/0056-sprint-38-internal-asset-inventory-source.md)
- **Base:** Sprint 37 PR #41 (`sprint-37-internal-ledger-source`)
- **Backlog:** BL-042 internal asset-position source only

## Objective

Add a verified, program-scoped snapshot of Badban's own persisted asset
positions. Preserve internal identity and ownership data while keeping this
source distinct from external custody and collateral-registry records.

## In scope

- Add the distinct `INTERNAL_ASSET_INVENTORY` snapshot and record contract.
- Read asset positions, types, and episode lineage in one PostgreSQL statement.
- Include a statement-time cutoff, evidence references, and canonical hash.
- Reject inconsistent scope, lineage, ownership, duplicates, or invalid data.
- Keep empty scope unavailable and all extraction read-only.
- Add unit and PostgreSQL integration coverage.

## Explicitly out of scope

- External custody, registry, issuer, or settlement adapters.
- Any comparison, case creation, freshness threshold, matching rule, tolerance,
  materiality, valuation decision, eligibility, allocation, or financial effect.
- BL-020, Stage, QA completion, Release, Production, and real-money behavior.

## Acceptance

- Only the explicitly registered internal source may provide this snapshot.
- Snapshot type, target, scope, schema, versions, evidence, hash, and timestamp
  pass the existing acquisition verification boundary.
- No source rows or ambiguous ownership creates no snapshot.
- Database integration coverage verifies program scoping and persisted facts.
- Keep the PR Draft/Open/unmerged through exact-head CI and code review.

## Verification result

- Four focused non-integration tests pass locally.
- Ruff, Pyright, format, and diff checks pass.
- Full GitHub CI run #496 passed on initial implementation head
  `cbb6e3576d07c9bb4fc6baa587cd7537fd4f9df6`, including PostgreSQL-backed
  tests, migration checks, dependency audit, container build, and secret scan.
- The PR remains Draft/Open/unmerged; code review is pending.
