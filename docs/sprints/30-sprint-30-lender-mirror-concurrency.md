# Sprint 30 — Multi-Replica Lender Mirror First-Event Concurrency Safety

- **Date:** 2026-10-09
- **Status:** Implementation; exact-head CI and technical Code Review pending
- **Base:** PR #32 Sprint 29, Code Review complete, exact-head CI #445 SUCCESS
- **Scope:** Backend only. Technical 08 event correctness and BL-041 multi-replica reliability hardening.

## Reproduced race condition

Before the first `ExternalLoanMirror` is persisted, a
`SELECT ... FOR UPDATE` on `(provider_id, external_loan_id)` acquires
**no row lock**. Concurrent workers can both observe missing data and
attempt conflicting inserts. This can generate an uncaught UNIQUE
constraint exception in an otherwise valid authenticated inbox processing
flow, risking delayed processing and noisy retries. A related race arises
when distinct external loan identifiers simultaneously attempt to claim
one GuaranteeCase.

## Contract / implementation

1. Derive a stable PostgreSQL **transaction-scoped advisory lock**
   namespace from `SHA-256("badban:lender:mirror:v1:" + provider_id.bytes
   + external_loan_id UTF-8)`, first signed 64 bits. This is not a
   business identity or cryptographic authorization; the existing
   persisted UNIQUE constraints remain the final integrity guard.
2. Acquire the lock **inside the same database transaction** as the
   inbox row and before any mirror SELECT/INSERT/UPDATE. This
   serializes both first creation and later updates from every worker
   replica using the same PostgreSQL database. It is automatically
   released upon transaction commit/rollback.
3. When first linking a mirror to a GuaranteeCase, lock that actual
   guarantee row with `FOR UPDATE`, verify matching provider identity,
   and reject a previously bound loan with a stable conflict code.
   Competing loan IDs cannot overwrite a GuaranteeCase linkage.
4. Keep normalized provider events as mirror/history facts only.
   Neither legal GuaranteeCase state nor journal/control balances are
   modified. No inferred risk PASS, loan approval, reserve or exposure.
5. Integration tests run genuine **concurrent database transactions**
   via `asyncio.gather`, exercising simultaneous first approved/
   disbursed observations for one loan and competing loans linked to
   one GuaranteeCase. Both cases prove rollback/uniqueness and lack of
   journal/guarantee effects. No fake Production provider/credentials.

## Non-goals / remaining dependencies

This does not implement BL-020, BL-026, BL-027 repayment, BL-028
exposure reduction, reservation, issuer integration or provider policy.
A provider and loan ID alone are never a legal authorization to finance.
Keep PR Draft/Open and no Merge, Stage, QA, Release, Production or Figma.
