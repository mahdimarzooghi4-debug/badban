# Sprint 28 — Technical Code Review

- **Status:** Technical Code Review complete; not independent Human Release Approval
- **Date:** 2026-10-09
- **PR:** #31 Draft/Open, stacked on PR #30
- **Reviewed code SHA:** `cf88bff62b332eb3cb8d36668c3e0d2c4648cc9b`
- **Full code CI:** #438 SUCCESS; 311 tests passed; Quality and Secret Scan successful
- **Scope:** partial guarantee operational read surfaces under accepted Technical 07 §19 and Technical 11

## Reviewed Implementation

### Program-scoped, bounded list

`GET /api/v1/guarantees?program_id=<uuid>` requires an authenticated
human staff identity and a currently valid Program or authorized GLOBAL
role grant for OPERATIONS, RISK, FINANCE_RECONCILIATION or AUDITOR.
The SQL query itself joins GuaranteeCase through ParticipationEpisode
and restricts `ParticipationEpisode.program_id` to the authorized
program. No unscoped cross-program list or count is exposed.

The cursor is persisted GuaranteeCase UUID, ordered monotonically by
`GuaranteeCase.id`, with `id > after` and a hard maximum page size
of 100. `limit + 1` is used solely to signal whether another page
exists. Optional exact persisted `state` filter never guesses state.
Missing authentication 401, unauthorized program 403 and malformed
limits/missing program IDs 422 are covered.

### Observed workspace context

`GET /api/v1/guarantees/{id}/workspace` first authorizes through the
existing Guarantee read permission and rebinds the actual Program in
the database query, refreshing ORM identity-map data. Guarantee,
episode, provider and captured immutable CreditProductVersion are
joined from authoritative persisted sources and their relationship
versions/mode/provider identities are explicitly checked. A missing
or contradictory source results in a stable 409, not a false workspace.

Only **REQUESTED** cases include the existing request-bound, multi-asset
valuation evidence. Cases in any other state expose persisted case
state but `request_evidence=null`: that does not mean lack of backing
or qualification. No valuations are inferred as current, no source
is automatically selected, and no capacity or Risk PASS is returned.

The ExternalLoanMirror is an **independent lender-originated read
model**, not a GuaranteeCase state transition. During review we found
that an authenticated lender event may persist a mirror with
`ExternalLoanMirror.guarantee_case_id` while
`GuaranteeCase.external_loan_mirror_id` is still NULL.
Original code incorrectly hid that real mirror. Code was corrected
to join the actual mirror's case link; if a populated reverse pointer
contradicts that relationship it fails closed with 409. Tests cover
both scenarios, including `REQUESTED` with observed PENDING mirror
and no automatic financial activation.

Explicit `false` contract availability fields mean **this slice does
not implement** backing allocation, claims/recovery, or permitted
action evaluation; they are not decisions about the specific case.

## CI and Regression Evidence

- #434 failed Ruff Format; exact reported formatting differences fixed.
- #435 failed Ruff Lint for unused import; removed.
- #436 full CI SUCCESS before mirror-link review improvement.
- #437 failed Ruff Format for revised consistency expression; fixed.
- #438 final reviewed code CI SUCCESS: **311 passed**, Quality and
  Secret Scan successful, tests, migrations, typing and container build.

OpenAPI and integration tests cover role/cross-program isolation,
required program and limit bounds, 5-record deterministic multi-page
traversal, empty state-filter result, full workspace source lineage,
REQUESTED versus non-REQUESTED behavior, mismatch errors, real
external mirror independent of reverse pointer, and contradictory
reverse mirror reference rejection.

## Known Gaps and Release Boundary

The two new endpoints are **a technical read foundation**, not the
full BL-045 operational workspace. Authorized actions, BackingAllocation
records and legal/claim/recovery summaries are not available because
the underlying financial transitions and business contracts remain
unimplemented. Role reads do not authorize financial commands.

The SQL reads are observed state, not a long-lived consistency lock
or authorization of later transactions. Mutable state may change
between HTTP queries. BL-020 remains blocked by unapproved selection,
holds, expiry, risk qualification, legal/custody and atomic
reservation behavior. No fabricated zeros or synthetic risk PASS
were introduced. Real provider and Production integration remain
separate gates.

`Code = COMPLETE`

`Technical Code Review = COMPLETE`

`Merge / Stage / QA / Release / Production = NOT AUTHORIZED`
