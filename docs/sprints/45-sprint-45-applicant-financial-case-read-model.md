# Sprint 45 — Applicant Financial Case Read Model

- **Status:** Implementation slice, stacked after Sprint 44.
- **Backlog:** BL-057.
- **Code authorization:** Decision 0063.

## Goal

Give each authenticated applicant one read-only view of their own three service records and distinct financial balances.

## Scope

- Resolve the participant through the verified national-ID claim established in Sprint 44.
- Read the participant's guarantee cases and linked lender loan mirrors.
- Read monthly pension entitlements and post-exit support cases/period entitlements.
- Return separate, currency-scoped principal, guarantee exposure, realized support return allocation, and allocated support totals.
- Show payment and external price-source integrations as not configured; do not invent payment evidence or zero balances.
- Bound result counts and ensure all queries are filtered by the resolved participant.

## Acceptance Criteria

1. The endpoint accepts no participant ID/reference from the caller and scopes every query to the verified participant.
2. Guarantee, monthly pension, and post-exit records are returned from their authoritative tables.
3. Monetary measures remain separate and are grouped by currency.
4. Only posted `RETURN_ALLOCATION@1` lines to the support buckets count as realized support return allocations.
5. Payment amounts remain null and payment status is explicitly `NOT_CONFIGURED` until settlement evidence exists.
6. Missing provider configuration is explicit, with no fabricated external values.

## Gates

- Exact-head CI and technical review are required.
- This is a read model; no payment, guarantee, or entitlement state can be changed here.
- No merge, Stage, release, or production operation is authorized.
