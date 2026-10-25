# Decision 0061 — Sprint 43 Post-Exit Support Lifecycle

- **Status:** Code authorized for the bounded Sprint 43 scope.
- **Authority:** Owner direction to continue Badban implementation against the supplied proposal.
- **Sources:** Business alignment (PR #50), service boundaries/backlog (PR #51), catalogue (PR #52), Sprint 42 monthly entitlement foundation (PR #53), ledger taxonomy and return-allocation templates.
- **Backlog:** BL-056.

## Decision

Implement a distinct exit-linked support case and period entitlement lifecycle for POST_EXIT_SUPPORT. The case records an authoritative exit-event reference, the exit date supplied from verified evidence, eligibility decision references, and a policy-bounded support duration. Each period uses a caller-supplied period reference and sequence number; no calendar interpretation or cadence is invented.

The support window is at most 36 periods and cannot exceed the active catalogue version's max_duration_months. An authorized operator supplies the proposed period amount, calculation reference, policy reference, and eligibility evidence. The service does not infer entitlement or calculate a benefit formula.

Each draft period entitlement must be fully backed by posted, unallocated RETURN_ALLOCATION@1 credits to 2020.FUTURE_FINANCIAL_ENTITLEMENT for the same participant and currency. A different authorized checker approves it. Approval does not initiate or assert payment.

## Controls

- A POST_EXIT_SUPPORT catalogue version must be ACTIVE, effective, policy-matched, and have a configured maximum duration from 1 through 36 months.
- Case creation requires a unique participant exit-event reference and evidence reference; no participation episode closure or financial reconciliation is treated as an exit event by inference.
- Period sequence starts at 1, cannot exceed the configured duration, and is unique within a support case.
- Funding is reserved transactionally from eligible, posted future-financial entitlement return postings; principal, forecasts, other service buckets, and unallocated returns are excluded.
- Case activation and each entitlement approval use maker-checker authorization and are audited.
- No payment/settlement endpoint, external provider, Stage, release, production operation, or merge is authorized.
