# Decision 0054 — Sprint 36 Verified Source Acquisition Boundary

- **Status:** Accepted — code scope only
- **Date:** 2026-10-25
- **Authorization:** User instruction to complete the remaining Badban work
- **Scope:** BL-042 technical source-acquisition boundary; no new business, legal, risk, or financial policy

## Decision

Authorize Sprint 36 to add an application boundary that acquires a canonical
reconciliation source snapshot only from an explicitly registered source port,
pins the port's `SourceCapability` at registration, and verifies source
identity, target, scope, schema, contract/mapping versions, evidence, hash, and
timestamp invariants before returning the snapshot to a caller.

Classify unavailable sources, timeouts, transport failures, and invalid source
contracts distinctly. Never return an unverified snapshot. A capability that
changes after registration is a non-retryable contract error.

## Constraints

- This boundary is read-only and performs no database writes, reconciliation
  comparison, case/run creation, policy selection, or financial mutation.
- No source is registered by default. Missing source remains
  `SOURCE_UNAVAILABLE`.
- No real or synthetic provider, legal authority, settlement, custody,
  collateral-registration, or ledger integration is asserted.
- No freshness threshold, matching rule, tolerance, materiality, or business
  outcome is introduced.
- Existing lender reconciliation and historical rows remain unchanged.
- This decision does not complete BL-042 or unblock BL-020/021/023/026, Stage,
  QA, Release, Production, or real-money operation.

## Consequences

Code may implement and document the verified acquisition boundary. The PR must
remain Draft/Open/unmerged through exact-head CI and code review. Separate
explicit source contracts and authoritative acquisition are still required
before any additional reconciliation vertical can execute.
