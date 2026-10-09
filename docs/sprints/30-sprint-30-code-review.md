# Sprint 30 — Technical Code Review

- **Status:** Technical Code Review COMPLETE (not an independent human approval)
- **Date:** 2026-10-09
- **PR:** #33 Draft/Open, stacked on PR #32
- **Reviewed exact code SHA:** `966e2a9df03419052149bb3e20352742b3740f82`
- **Exact-head code CI:** #447 SUCCESS — 317 backend tests passed, 1 existing warning, Quality and Secret Scan SUCCESS
- **Scope:** Backend multi-replica correctness under Technical 08 / BL-041, not commercial approval

## Root cause and change

Prior worker code performed `SELECT ExternalLoanMirror ... FOR UPDATE`
but the first lender event sees no mirror row to lock. Concurrent inbox
transactions could each attempt to INSERT the same
`(provider_id, external_loan_id)`, producing a database UNIQUE
violation despite valid source events. An uncaught DB exception could
stop a processing batch and introduce retries that do not represent
a provider/business conflict.

The reviewed fix derives a stable **signed 64-bit advisory lock key**
from SHA-256 over a versioned namespace, provider UUID bytes and lender
external loan identifier. `pg_advisory_xact_lock` is acquired in the
**same transaction** as the inbox-row lock and source/historical
mirror writes, before selecting the mirror. All worker replicas
pointing at the same PostgreSQL database serialize this identity
regardless of whether the first row exists. Commit/rollback releases
the advisory lock. Original UNIQUE constraints stay in place.

For first-event attempts to bind a GuaranteeCase, the handler also
obtains the actual GuaranteeCase row lock, verifies matching Provider
identity, and checks if a different existing mirror already claims
the same case. An independent competing external loan then raises
`LENDER_GUARANTEE_LINK_CONFLICT` rather than silently overriding
the linkage or leaking a provider-side IntegrityError.

## Real-database concurrency tests

1. Stable provider-and-loan-scoped advisory key derives the same
   result for identical inputs and differs across independent
   providers/loan identifiers.
2. Two independently accepted, authenticated inbound events for the
   same previously unknown external loan are processed with actual
   parallel PostgreSQL transactions. Both complete safely, producing
   **one mirror**, **two immutable event records**, both inbox messages
   processed, and no additional GuaranteeCase transition or Journal
   entry. Reversed initial observation order is handled by the existing
   stale/event-sequence safeguards, not by inferring an approval.
3. Two independently authenticated loan IDs concurrently competing
   for one actual GuaranteeCase: exactly one creates a mirror, the
   other returns the stable link conflict, and its inbox item remains
   unprocessed for explicit investigation. One history record exists;
   no journal or GuaranteeCase mutation occurs.
4. Prior borrower/lender state, sequence gap, stale correction,
   inbox replay/idempotency, provider scope and financial
   non-mutation integration regression continue to pass.

## CI trace

- #446: Ruff formatting differences only — corrected.
- #447: complete exact-code SHA CI SUCCESS: **317 passed**, Quality
  checks, PostgreSQL test suite, migrations, type checking,
  container build and Secret Scan all green.

## Residual limits

- Database advisory locks protect operations through this same
  processing primitive on the same PostgreSQL cluster. They do not
  solve cross-system provider authentication, business authorization,
  network partitions, a provider sending contradictory independent
  facts, or real-time lender reconciliation.
- Validated source events **only** update ExternalLoanMirror and its
  append-only observed history. They do not activate GuaranteeCase,
  reduce exposures, reserve collateral or post Badban journals.
- A competing loan's rejected Inbox row remains unprocessed; no
  invented automatic correction or dead-letter policy is introduced.
  Out-of-order event gaps still require actual missing events or
  human-controlled recovery.
- Business-dependent BL-020 and guarantee issuance/activation
  BL-021/023/026 remain blocked; BL-027 repayment and BL-028 exposure
  reduction are not implemented by this fix. No Stage/QA/Release/
  Production or Figma work authorized.

`Code = COMPLETE`

`Technical Code Review = COMPLETE`

`Merge/Stage/QA/Release/Production = NOT AUTHORIZED`
