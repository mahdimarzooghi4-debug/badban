# Decision 0061 — Sprint 43 Post-Exit Support Lifecycle

- **Status:** Code authorized for the bounded Sprint 43 scope.
- **Authority:** Owner direction to continue Badban implementation against the supplied proposal.
- **Sources:** Business alignment (PR #50), service boundaries/backlog (PR #51), catalogue (PR #52), Sprint 42 monthly entitlement foundation (PR #53), ledger taxonomy and return-allocation templates.
- **Backlog:** BL-056.

## Decision

Implement a distinct exit-linked support case and period entitlement lifecycle for POST_EXIT_SUPPORT. The case records an authoritative exit-event reference, the exit date supplied from verified evidence, eligibility decision references, and a policy-bounded support duration. Each period uses a caller-supplied period reference, sequence number, and timestamp. The timestamp must be within the policy-defined window calculated from the configured start date and duration. No payment cadence is inferred.

The support duration is at most 36 months and cannot exceed the active catalogue version's max_duration_months. Its calculated end must also fall no later than exit date plus the configured maximum. An authorized operator supplies the proposed period amount, calculation reference, policy reference, and eligibility evidence. The service does not infer entitlement or calculate a benefit formula.

Each draft period entitlement must be fully backed by posted, unallocated RETURN_ALLOCATION@1 credits to 2020.FUTURE_FINANCIAL_ENTITLEMENT for the same participant and currency. A different authorized checker approves it. Approval does not initiate or assert payment.

## Controls

- A POST_EXIT_SUPPORT catalogue version must be ACTIVE, effective, policy-matched, and have a configured maximum duration from 1 through 36 months.
- Case creation requires a unique participant exit-event reference and evidence reference; no participation episode closure or financial reconciliation is treated as an exit event by inference.
- Period sequence starts at 1, cannot exceed the configured duration, and is unique within a support case.
- Funding is reserved transactionally from eligible, posted future-financial entitlement return postings; principal, forecasts, other service buckets, and unallocated returns are excluded.
- Case activation, suspension/resumption/completion/cancellation, and each entitlement approval require an authorized actor other than the case creator and are audited.
- No payment/settlement endpoint, external provider, Stage, release, production operation, or merge is authorized.
