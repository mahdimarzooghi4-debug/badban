# Decision 0052 — Sprint 25 Request-bound Backing Evidence

- **Status:** Accepted, technical read-only contract ONLY
- **Date:** 2026-10-09
- **Prerequisite:** Sprint 24; exact-head CI #414 SUCCESS
- **Target:** BL-020 source/lineage preparation, NOT BL-020 transition authorization

## Authorized Data Flow

Build a single-statement internal PostgreSQL projection of a *specific* persisted
REQUESTED GuaranteeCase, its ParticipationEpisode/Program, captured external
CreditProvider/CreditProductVersion, and every persisted AssetPosition/AssetType/
ValuationObservation for that episode. Reuse the Sprint 24 evidence assembly.

Report authoritative stored IDs, aggregate/product versions, actual provider/
product lifecycle states, exact requested principal, product range/currency/
guarantee mode and asset ownership/valuation records. Do **not** interpret
whether those states authorize reservation. Preserve product policy reference
as historical lineage only, not an executable or selected policy.

## Fail Closed

- missing guarantee, wrong program, inconsistent product/provider ID or
  guarantee mode, or invalid version blocks the projection;
- state other than REQUESTED or REQUESTED with populated reservation/exposure
  fields blocks projection;
- source inventory cross-program/ownership/unit contradictions remain blocked.

Any hash is a fingerprint of observed fields, not cryptographic verification of
the provider, approval, freshness, transaction integrity, or a reservation lock.

## Boundaries

No new API or authorization relaxation; no writes, allocation/selection,
credit-product decision, valuation approval, risk PASS, capacity calculation,
reservation expiry, transition, journal/audit/outbox effects or provider calls.

BL-020 remains BLOCKED on approved multi-asset allocation, sources/holds,
expiry derivation, risk snapshot qualification and transaction contract.
No Merge, Stage, QA, Release, Production or real-money behavior.
