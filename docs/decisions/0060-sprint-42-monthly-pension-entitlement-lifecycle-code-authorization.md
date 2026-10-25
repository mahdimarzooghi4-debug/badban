# Decision 0060 — Sprint 42 Monthly Pension Entitlement Lifecycle

- **Status:** Code authorized for the bounded Sprint 42 scope.
- **Authority:** Project owner direction to continue Badban against the supplied proposal and complete the backend.
- **Sources:** Business alignment (PR #50), technical service boundaries and backlog (PR #51), catalogue foundation (PR #52), Technical 05 return-allocation and livelihood-payment rules.
- **Backlog:** BL-055.

## Decision

Implement a monthly pension entitlement workflow funded only from posted `RETURN_ALLOCATION@1` journal postings to `2010.LIVELIHOOD_PAYABLE` for the same participant and currency. The source posting must be verified as POSTED. Each amount is reserved against one or more source postings in the same transaction, so the same allocated livelihood amount cannot be assigned twice.

An authorized operator supplies the policy-defined period reference, approved policy version, eligibility evidence reference, calculation reference, and proposed amount. The system records that decision and source lineage; it does not invent eligibility or amount formulas.

A separate authorized checker approves the entitlement. Approval does not send money or mark it paid. Payment remains unavailable until a verified settlement flow exists. Entitlement amounts cannot be sourced from principal, forecast return, or unallocated income.

## Controls

- An active/effective `MONTHLY_PENSION` service catalogue version and matching policy reference are required.
- Duplicate participant/period entitlements are rejected; retries use idempotency.
- Maker and checker must be different identities.
- Source journal entries are locked during allocation reservation; allocation totals cannot exceed their posted livelihood-payable source lines.
- Applicant self-service is not exposed until participant-to-identity ownership is explicitly modeled.
- No external payment source, Stage, release, production operation, or merge is authorized by this decision.
