# Sprint 51 — Supporting Institution Financial Case

## Goal

Give a support institution operator a useful beneficiary financial view while preserving strict program and episode boundaries.

## Deliverables

- Read-only financial-case endpoint scoped to an active exact-program role grant.
- Asset positions filtered by both program and participation episode, including participant-owned versus program-attributed classification.
- Source-stamped valuation observations, including freshness, observation time, and currency.
- Guarantee status and amounts, plus provider-linked reported loan status/outstanding principal.
- Audit event for every successful read.

## Explicit limits

- The request must identify a participant and episode, and the episode must belong to that participant and program.
- The endpoint does not return national ID or contact data.
- Valuation observations are historical/source-reported facts, not a selected quote.
- Profit share and the monthly-pension/post-exit services are omitted from this program view until explicit program lineage is modeled.
- Read-only; no enrollment, eligibility, approval, payment, or record mutation.

## Validation

- GitHub Actions is the validation gate for this branch; no local test run.
