# Decision 0056 — Sprint 38 Internal Asset Inventory Source

- **Status:** Accepted — code scope only
- **Date:** 2026-10-25
- **Authorization:** User direction to finish remaining internal-source work while unidentified external systems remain fail-closed
- **Scope:** Read-only snapshot of persisted Badban asset-position inventory

## Decision

Authorize a distinct `INTERNAL_ASSET_INVENTORY` source over existing
`AssetPosition`, `AssetType`, and `ParticipationEpisode` rows. The snapshot is
program-scoped and preserves the position ID/version, asset type, quantity and
unit, lifecycle, custody-entity reference, and existing ownership dimensions.
Snapshot time is read from PostgreSQL `statement_timestamp()` in the same
statement as the source rows.

## Constraints

- This source represents only Badban's own persisted asset-position inventory.
  It is not a custody, collateral-registry, legal-ownership, valuation, or
  external-provider attestation.
- No rows in scope means `SOURCE_UNAVAILABLE`; no zero position is synthesized.
- Inconsistent program, episode, asset-type, or owner lineage fails closed.
- Read-only extraction only: no comparisons, reconciliation cases, financial
  eligibility, allocation, restriction, reserve, journal, or external calls.
- Issuer, custody, settlement, and collateral-registry source integrations
  remain unavailable until authoritative systems are identified. BL-020 remains
  blocked pending explicit allocation/restriction/risk decisions.
- Keep the PR Draft/Open/unmerged through exact-head CI and code review.
