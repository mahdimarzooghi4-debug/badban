# Sprint 34 — Technical Code Review: Stable Outbox JetStream Identity

- **Reviewed Code HEAD:** `6841ec73d8b2fc93ea16a19f4970b35a0c4438b6`
- **Code CI:** [#465](https://github.com/mahdimarzooghi4-debug/badban/actions/runs/37943183676) **SUCCESS**, 329 tests passed, 1 pytest warning, Ruff Format/Lint, Pyright 0 errors/warnings, PostgreSQL migration/drift, Dependency Audit, Container Build, Secret Scan all SUCCESS
- **Status:** Automated Technical Code Review COMPLETE; independent human approval is not asserted.
- **Dependency:** PR #36 Draft/Open, CI #463 green; PR #37 stays stacked Draft/Open.

## Reviewed invariants

1. **Stable identity:** immutable persisted Outbox UUID is supplied verbatim as an optional `message_id` keyword to the internal publisher protocol and converted to the standard `Nats-Msg-Id` JetStream publish header. Payload envelope, `event_id`, aggregate/version and correlation/causation remain unchanged.
2. **Crash/retry:** real broker integration simulates successfully acknowledged JetStream publish followed by worker cancellation before PostgreSQL commits `published_at`. The Outbox remains pending with no persisted delivery attempt; the subsequent retry uses the original UUID and broker sequence. Exactly one broker record within the configured duplicate window is proved in the test, with a distinct ID adding a second sequence.
3. **Exact limitations:** JetStream deduplication is bounded by the server-configured duplicate window, not a permanent idempotency guarantee. No window duration or retry algorithm is selected/modified by this Sprint. Existing consumers must continue idempotent processing of immutable `event_id`; **at-least-once delivery remains the contract**.
4. **Safety:** the unchanged transactional Outbox continues `FOR UPDATE SKIP LOCKED`, post-broker-ack status mutation and failure preservation; NATS transport is a narrow adapter, with no new financial/guarantee command, provider integration, credential, dead-letter action or invented policy.
5. **Compatibility:** direct JetStream transport callers not supplying `message_id` retain their behavior. Tests cover optional omitted ID, invalid blank ID, repeated ID, and original outbox/failure/concurrency semantics. All changes are within the existing accepted BL-041/BL-051 framework; no DB schema migration.
6. **Security review:** message identity is the existing internal UUID, not an external provider identifier or secret; no new log payload/credential emission. Messages still carry the existing envelope security classification and retain consumer access restrictions.

## Scope limits

- The duplicate-window duration is configured on JetStream and intentionally not supplied or changed by this patch. Duplicates can recur after the window or on broker configuration changes, so permanent deduplication is **not** claimed.
- No real external lender, PSP, issuer or custodian integration is implied.
- No Stage, QA Gate, Release, Production or Figma was executed.
- This automated code review is not independent human signoff.

## Disposition

**Technical Code Review complete for the bounded code HEAD; no code blockers identified after green CI #465.** The final documentation commit must undergo its own exact-SHA CI, and PR #37 remains Draft/Open/Unmerged.
