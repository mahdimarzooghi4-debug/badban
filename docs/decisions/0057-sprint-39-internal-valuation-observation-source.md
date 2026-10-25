# Decision 0057 — Sprint 39 Internal Valuation Observation Source

- **Status:** Accepted — code scope only
- **Date:** 2026-10-25
- **Authorization:** User direction to continue the remaining internal-source work
- **Scope:** Read-only snapshot of valuation observations already recorded in Badban

## Decision

Authorize a distinct `INTERNAL_VALUATION_OBSERVATION` source over persisted
`ValuationObservation` rows joined to their `AssetPosition` program lineage.
Each stored observation is returned independently with its original source
labels, amounts, timestamps, validity date, recorded freshness state, and
evidence reference. Snapshot time is read using PostgreSQL
`statement_timestamp()` in the same statement.

## Constraints

- This source reports only what Badban has recorded. It does not authenticate
  or independently verify the named valuation provider or source reference.
- The adapter preserves `freshness_status` and `valid_until` as stored facts; it
  does not decide whether an observation is fresh, valid, or eligible.
- No source rows means `SOURCE_UNAVAILABLE`; future observations, wrong-program
  lineage, or malformed values fail closed.
- Read-only extraction only: no valuation selection, asset eligibility,
  reconciliation comparison/cases, financial decision, or external call.
- External issuer, custody, settlement, and registry sources remain
  unavailable until an authoritative system is identified. BL-020 remains
  blocked pending explicit allocation/restriction/risk decisions.
- Keep the PR Draft/Open/unmerged through exact-head CI and code review.
