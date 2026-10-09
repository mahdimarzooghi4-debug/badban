# Decision 0051 — Sprint 24 Read-only Backing Source Inventory

- **Status:** Accepted — technical evidence-projection authorization only
- **Date:** 2026-10-09
- **Source:** Decisions 0001, 0003, 0008; Technical 04; BL-020 readiness review
- **Baseline:** Sprint 23 Draft/Open exact-head CI #410 SUCCESS

## Authorization

Build an internal read-only projection of current persisted ParticipationEpisode,
AssetPosition, AssetType and all stored ValuationObservation source facts for one
explicit episode/program pair. Use a single PostgreSQL statement to avoid
different source reads drifting across statements. Produce sorted typed records
and a deterministic evidence *inventory fingerprint*, not a capacity or lock proof.

## Required Boundaries

- Preserve multiple asset positions, exact quantity, unit, ownership/funding
  classification, legal owner and custodian references, lifecycle, type and
  aggregate versions, without hard-coding Gold.
- Preserve *all* valuation observations with their recorded timestamps,
  currency, exact decimals, source/lineage and persisted freshness labels.
  Do not choose a current/canonical valuation or infer freshness eligibility.
- Reject cross-program/episode lineage, unit and owner-integrity contradictions;
  do not infer missing data. Missing valuations stay absent, never zero/fresh.
- Do not calculate gross/available capacity, eligibility, pledgeability,
  allocated amounts, risk PASS, backing selection, reservation or expiry.
- Do not expose a new HTTP endpoint or bypass existing role authorization.
- No database migration, transaction mutation, external provider or policy values.

## Context and Limitations

The fingerprint attests only to this source projection's serialized fields. It
is not an independent source-signature, accepted valuation, policy acceptance,
or reservation concurrency lock. A later reservation transaction must re-read
and lock/check actual authoritative state under the approved contract.

## No Product Authorization

BL-020, BL-016, BL-021, BL-023, BL-026, BL-033 and BL-034 are not unblocked
by this technical capability alone. No Merge, Stage, QA, Release or Production.
