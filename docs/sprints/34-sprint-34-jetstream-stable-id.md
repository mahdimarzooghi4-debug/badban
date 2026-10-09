# Sprint 34 — Stable JetStream Publication Identity / Crash-Replay Safety

- **Date:** 2026-10-09
- **Scope:** Backend BL-041 and BL-051 — at-least-once Outbox safety hardening
- **Base:** Sprint 33 PR #36, final HEAD `3d344b8db6e5341723023357dd78198bd9dedb83`, exact-head CI #463 SUCCESS
- **State:** Draft PR; code, full CI, automated Technical Code Review pending

## Issue and exact limited contract

An Outbox row can be successfully acknowledged by JetStream while the
surrounding PostgreSQL transaction has not yet committed `published_at`.
Following worker interruption, that Outbox row is correctly retried,
but previously the transport lacked the stable `Nats-Msg-Id` header;
the Broker could store two separate copies in short succession.

Extend the existing `EventPublisher.publish` protocol with an **optional**
keyword `message_id`. The Outbox publisher supplies the immutable UUID
of each persisted Outbox event, and the real NATS JetStream transport sends
that ID verbatim in its `Nats-Msg-Id` header. The event schema/payload and
original ID remain unchanged. Direct transport publishing without a
message ID remains compatible with existing callers.

NATS JetStream deduplicates matching message IDs only **within its
configured duplicate window**. We do not select, change or invent a
Production duplicate-window duration. We do **not** claim exactly-once
transport or permanent broker deduplication; all consumers MUST continue
to deduplicate events by immutable `event_id`. Post-window repeats
are allowed by at-least-once semantics.

## Scope and boundaries

- Real broker integration proves same event ID + duplicate publish obtains
  unchanged stream sequence, and a distinct ID obtains a new sequence.
- Failure injection acknowledges the first publish but cancels the worker
  before PostgreSQL commit; Outbox remains pending and the second publish
  reuses the same JetStream identity and original envelope.
- Preserves existing database skip-locked concurrency,
  post-ack publication semantics and handler atomicity.
- No new provider credentials, secret, automatic dead-letter, replay command,
  retry threshold, alert threshold, financial logic, guarantee/risk command,
  Stage, QA, Release or Production deployment.
- Backend code, tests and documentation only; no migration or Figma.
