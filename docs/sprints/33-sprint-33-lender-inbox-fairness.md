# Sprint 33 — Durable Fair Lender Inbox Scanning

- **Date:** 2026-10-09
- **Scope:** Backend BL-041/BL-051 lender Inbox starvation and multi-replica reliability
- **Base:** Sprint 32 PR #35 exact-head CI #457 SUCCESS
- **State:** Code and automated Technical Code Review complete; Draft/Open PR #36, unmerged

## Confirmed defect

`process_pending_lender_inbox_batch` always queried the first N unprocessed
lender Inbox events ordered by `(received_at,id)`. A permanent error in the
oldest N messages repeatedly selected the same prefix and could starve valid
later events indefinitely. A local-only pagination cursor would reset on
restart and diverge across replicas.

## Contract

- Persist one `lender_inbox_scan_checkpoints` cursor (stream `lender-inbox:v1`)
  containing immutable Inbox `(received_at,id)` position. A PostgreSQL
  transaction row lock protects a single advancement across all replicas.
- Each bounded query advances after the previous cursor and wraps only when
  insufficient later pending events exist. Every nonprocessed lender Inbox
  remains eligible for later scans, including sequence gaps and failed rows.
  A scan checkpoint commits before handler execution so failure does not
  rewind the cursor and starve peers.
- Original transactional Inbox handler maintains per-message row locking,
  idempotency, authoritative mirror writes and outbox atomicity. A crash after
  checkpoint commit cannot lose a message: it remains `processed_at=NULL`
  and the scanner eventually wraps to it.
- No automatic quarantine, retry limit, fixed retry time, dead-letter cutoff,
  provider identity invention, financial ledger mutation or fabricated
  risk/guarantee transition. The checkpoint is scheduling metadata only,
  not an acknowledgment or source of truth.
- Indexed pending Inbox scan; migration `20261009_0020` after
  `20261009_0019`; test fixture cleanup also resets checkpoint state.

## Tests

PostgreSQL integration: poison messages at head cannot starve valid real
LOAN_APPROVED events; cursor persists across a recreated Database/worker;
multiple scanner replicas get disjoint pages while enough pending events
exist; failed message remains retryable after wrap; processed rows skip;
invalid checkpoint pair is rejected by DB constraint; batch validation and
empty path. No provider credentials/real provider network, Stage or QA.

## Review and exact-SHA code evidence

- Code HEAD: `32169b303c19351286c20eb2ed4dc671f0775973`
- [Full code CI #462](https://github.com/mahdimarzooghi4-debug/badban/actions/runs/37941523784): SUCCESS, 327 passed (1 warning), Quality / Secret Scan green
- [Automated Technical Code Review](./33-sprint-33-code-review.md) recorded on reviewed code SHA
- Final documentation HEAD requires separate exact-head CI before closure; no Merge, Stage, QA, Release or Production.
