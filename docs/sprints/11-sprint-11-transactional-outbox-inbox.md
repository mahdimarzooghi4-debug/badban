# Sprint 11 — Transactional Outbox / Inbox Hardening

- **Status:** Accepted
- **Date:** 2026-10-07
- **Stage:** Sprint Planning
- **Scope:** integration reliability foundation
- **Entry Gate:** Sprint 10 / BL-031 merged; post-merge CI #249 green
- **Depends on:** BL-004; Technical 08
- **Code Authorization:** GRANTED BY DECISION 0036

## 1. Sprint Goal

Complete **BL-041 — Transactional Outbox / Inbox** on the existing Sprint 01 foundation.

The Sprint must provide at-least-once integration delivery with exactly-once business effect, without inventing provider authentication, retry thresholds, or public event-injection APIs.

## 2. Outbox Contract

Outbox event facts are immutable after insert:

- event ID;
- event type;
- event version;
- aggregate type;
- aggregate ID;
- aggregate version;
- payload;
- correlation ID;
- causation ID;
- occurred time.

Delivery metadata may change independently:

- published time;
- publish attempt count;
- last delivery error;
- next attempt time;
- dead-letter time/reason;
- replay count.

The database must reject mutation of immutable event facts.

## 3. Delivery Contract

The worker must:

- select unpublished, non-dead-lettered, due outbox rows;
- use database row locking / skip-locked semantics so multiple workers do not concurrently claim the same row;
- publish a versioned event envelope through the existing broker abstraction;
- mark the row published only after broker acknowledgement;
- on publish failure, preserve the event, increment attempt metadata, store a bounded error description, and schedule a later retry;
- tolerate publish-success / database-commit-failure by allowing duplicate delivery on retry.

Exactly-once transport must not be claimed.

## 4. Dead-Letter and Replay

Dead-letter is explicit in Sprint 11.

Requirements:

- original event facts remain unchanged;
- dead-letter requires reason and accountable actor;
- dead-letter is audited;
- replay requires accountable actor and reason;
- replay preserves the same business event ID;
- replay clears only delivery blocking metadata needed to retry and increments replay count;
- replay is audited.

No automatic dead-letter attempt limit is introduced.

## 5. Inbox Contract

Authenticated and normalized provider events are recorded using the existing uniqueness scope:

`source/provider + event type + external event ID`.

Rules:

- same identity + same payload hash returns the existing inbox result;
- same identity + different payload hash fails closed as a conflict;
- concurrent duplicate delivery creates at most one inbox row;
- raw unauthenticated provider payload is outside this primitive;
- no provider-specific authentication is faked.

## 6. Exactly-Once Business Effect Primitive

Inbox processing must:

- lock the inbox row;
- return already-processed status without invoking the handler again when `processed_at` is already set;
- invoke the domain/application handler inside the same database transaction;
- set `processed_at` only after handler success;
- roll back both handler effects and `processed_at` when the handler fails;
- support safe retry after crash/failure.

The handler must use normal domain/application commands. It must not directly mutate financial ledger balances.

## 7. Event Envelope

Outbound event serialization must contain at least:

- `event_id`;
- `event_type`;
- `event_version`;
- `aggregate_type`;
- `aggregate_id`;
- `aggregate_version`;
- `correlation_id`;
- `causation_id`;
- `occurred_at`;
- `payload`.

Money/quantity values already present in payloads remain decimal strings.

## 8. Worker Integration

The existing worker may be extended to run an outbox publisher loop.

Requirements:

- dependency check remains available;
- graceful shutdown remains supported;
- no provider-specific consumer is added;
- no public generic event-ingress HTTP endpoint is added;
- the worker remains safe for multiple replicas.

## 9. Tests

Tests must cover:

- state change + outbox rollback atomicity;
- successful publication and published timestamp;
- broker failure leaves event pending with incremented attempt metadata;
- two concurrent publishers do not publish the same row concurrently;
- explicit dead-letter + audit;
- explicit replay + same event ID + audit;
- inbox same-payload duplicate returns existing row;
- inbox same identity / different payload fails closed;
- concurrent inbox duplicate is race-safe;
- handler executes once for duplicate delivery;
- handler failure rolls back business effect and inbox completion;
- retry after failure executes once and then becomes processed;
- no generic public event injection endpoint.

## 10. Explicit Non-Goals

No BL-020, BL-021, BL-022, BL-024, BL-033, reconciliation engine, provider authentication implementation, provider credentials, automatic dead-letter threshold, Stage pass, QA pass, Release Approval, Production, or real-money behavior.

## 11. Definition of Done

BL-041 is Done through Code Review when the outbox publisher, immutable event protection, delivery metadata, explicit dead-letter/replay, race-safe inbox deduplication, exactly-once business-effect primitive, worker integration, migrations, and tests are complete and full CI is green.
