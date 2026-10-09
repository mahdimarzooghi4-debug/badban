# Sprint 33 — Technical Code Review: Durable Lender Inbox Fairness

- **Date:** 2026-10-09
- **Reviewed Code HEAD:** `32169b303c19351286c20eb2ed4dc671f0775973`
- **Full Code CI:** [#462](https://github.com/mahdimarzooghi4-debug/badban/actions/runs/37941523784) **SUCCESS** — 327 tests passed (1 pytest warning); Ruff Format, Lint, Pyright (0 errors/0 warnings), PostgreSQL migrations and drift, Dependency Audit, Container Build, Secret Scan all successful.
- **Status:** Automated technical Code Review completed; independent human review/approval **not** asserted.
- **Branch:** Draft PR #36 stacked on Sprint 32 Draft PR #35, unmerged.

## Reviewed invariant boundaries

1. **Head-of-line starvation corrected:** the previous every-poll `ORDER BY received_at,id LIMIT N` repeatedly selected the same unprocessable oldest N entries. The new cursor advances after selection and wraps when necessary, so later accepted events become reachable even with permanently failing older rows. Two malformed real Inbox messages cannot block two later valid normalized loan events (PostgreSQL acceptance test).
2. **Crash safety:** position is scheduling-only and committed separately from handler execution. An event selected immediately before a crash remains `processed_at=NULL` until its authoritative handler commits; next scan cycles can wrap back to it. No message is deleted or acknowledged just for scanning.
3. **Multi-replica correctness:** a unique single-row PostgreSQL checkpoint and `SELECT ... FOR UPDATE` serialize page selection across independent Worker replicas; the three-scanner concurrency integration test observes disjoint pages for six eligible Inbox entries. Independent handler retains per-message row lock and atomic business-outbox transaction to protect duplicate selections near wrap.
4. **Source integrity:** `InboxMessage` event facts remain immutable, authenticated source identity and external event id deduplication unchanged. A new index accelerates pending-message scans; new checkpoint table has a DB constraint requiring timestamp and UUID pair to be either both populated or both NULL.
5. **Sequence-gap correctness:** provider stream gap still fails closed until its missing predecessor arrives. The prior integration test was corrected to allow the missing event and deferred event to complete within one batch (rather than assume a fixed number of worker polls). It still verifies no outstanding Inbox records for the test stream.
6. **No new risk/financial policy:** no retry ceiling, quarantine, dead-letter cutoff, TTL, invented provider contract, auto-risk PASS, guarantee reservation or journal movement. Real provider credentials were not supplied. No model/code bypasses existing `process_inbox_message_once` invariants.

## Limitations

- Scanner fairness is global across the existing `lender:` source namespace; it is **not** a per-provider or per-loan strict ordering guarantee. Individual normalized provider events still enforce their own authoritative predecessor checks and can retry after a sequence gap.
- If only poison records remain, they continue to be tried on future scans; this package does not define automatic quarantine, dead-letter/replay threshold, or custom retry cadence. Operational policy requires separate explicit approval.
- A selected page commits before business processing, so concurrent replicas can reselect the same still-unprocessed item after wrap when the pending set is smaller than their combined batches. Existing Inbox row locks protect business-effect uniqueness; the scanner does not promise exactly-once **attempts**.
- Stage, QA, Release, Production, real-money flows and Figma have not been authorized or executed.

## Disposition

**Code / PostgreSQL tests / automated Technical Code Review complete for the bounded scope.** PR remains Draft/Open; Merge and independent human review still require user decision. The additional review documentation commit requires its own exact-head CI pass.
