# Sprint 42 — Monthly Pension Entitlement Lifecycle

- **Status:** Implementation slice, stacked after Sprint 41.
- **Backlog:** BL-055.
- **Code authorization:** Decision 0060.
- **Financial source:** posted `RETURN_ALLOCATION@1` lines to `2010.LIVELIHOOD_PAYABLE`.

## Sprint Goal

Create an auditable, policy-bound monthly pension entitlement workflow that reserves only already allocated livelihood returns and prevents duplicate allocations.

## In Scope

- Persist one participant entitlement per policy-defined period, with source journal and allocation lineage.
- Create a draft entitlement only when a matching active/effective `MONTHLY_PENSION` catalogue version and matching policy references exist.
- Verify each source as a POSTED return-allocation journal line to the participant's livelihood-payable account in the same currency.
- Atomically reserve the requested amount across listed sources, with row locks and idempotent requests.
- Add maker-checker approval; the approver must differ from the maker.
- Record approval and audit history without creating a payment or marking an entitlement paid.
- Add admin read models for draft, approved, and cancelled entitlements.
- Add migration and API documentation.

## Out of Scope

- Eligibility, amount, rounding, or policy formulas. These are provided as approved policy/calculation references and explicit reviewed inputs.
- Calendar interpretation or automatic period generation; the policy-defined period reference is captured verbatim.
- Payment instruction, settlement, reversal, or paid state.
- Participant self-service until identity ownership mapping exists.
- External APIs, Stage, release, or production.

## Acceptance Criteria

1. A draft requires matching active/effective monthly service and policy versions.
2. Every funding source is a posted `RETURN_ALLOCATION@1` journal posting to `2010.LIVELIHOOD_PAYABLE`, for the same participant and currency.
3. Total active reservations from a source posting never exceed its posted credit.
4. Source posting locks prevent concurrent requests from double-allocating return.
5. Duplicate participant/period creation and idempotent replay behave deterministically.
6. Only a different authorized checker can approve; approvals are auditable and immutable.
7. No endpoint can mark an entitlement paid or create a settlement record.
8. Migration upgrade/downgrade preserves all existing financial records.

## Gates

- Exact-head CI and code review are required.
- Sprint 42 remains Draft/unmerged. No Stage or release is authorized.
