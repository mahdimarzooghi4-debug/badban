# Decision 0036 — Sprint 11 Transactional Outbox / Inbox; Code Authorization

- **Status:** Accepted
- **Date:** 2026-10-07
- **Scope:** Sprint 11 / Integration Reliability / Code Authorization
- **Depends on:** BL-004; Technical 08; post-merge CI #249 green
- **Authorizes:** BL-041 only

## Decision

Accept Sprint 11 and authorize Code only for:

- **BL-041 — Transactional Outbox / Inbox**

## Rationale

The repository already has the Sprint 01 outbox/inbox persistence foundation and NATS JetStream transport, but the accepted Technical 08 delivery contract is not yet complete.

BL-041 is selected before BL-033 and BL-020 because it is a P1 platform dependency with an explicit accepted contract and does not require inventing unresolved business values.

BL-020 remains blocked on explicit allocation, reservation-expiry derivation, and risk-snapshot qualification/freshness semantics.

BL-033 is not part of Sprint 11. Its reserve-account persistence may be implemented later, while actual claim-linked reserve draw remains coupled to the authorized claim/settlement flow and must not be invented as a generic financial command.

## Authorized Scope

Sprint 11 may implement:

- immutable business-event facts in outbox rows;
- mutable delivery metadata separated from immutable event facts;
- transactional outbox publication using at-least-once semantics;
- multi-worker safe selection using database locking;
- retry metadata and retry scheduling after transport failure;
- explicit dead-letter command with reason and audit;
- explicit replay command preserving the original business event identity;
- race-safe provider inbox deduplication by source/provider + event type + external event ID;
- same-key/different-payload conflict detection;
- an inbox processing primitive that binds business effect and inbox completion to one database transaction;
- crash/retry safety tests;
- worker integration with the existing NATS JetStream transport;
- event-envelope serialization with event ID, version, aggregate identity/version, correlation, causation, occurrence time, and payload.

## No Invented Retry Threshold

No business/operational dead-letter retry limit is approved by this Sprint.

Automatic transition to dead-letter based on a guessed attempt count is forbidden.

Dead-letter and replay are explicit operational commands in this Sprint. Future runtime configuration may define an automatic retry/dead-letter policy only after it is explicitly approved.

## Provider Authentication Boundary

Sprint 11 does not fake provider authentication.

The inbox acceptance primitive consumes only an event already authenticated and normalized by an adapter boundary. BL-022/BL-024 remain responsible for provider-specific authentication/normalization contracts.

## Financial Safety

Inbound integration handlers must not directly mutate ledger balances.

Financial/control effects must continue through idempotent application/domain commands.

Exactly-once transport is not claimed. The target is:

`at-least-once delivery + exactly-once business effect`.

## API Boundary

No public generic event injection endpoint is authorized.

Dead-letter/replay may remain internal application/worker capabilities until an explicitly authorized operations API/workspace exists.

## Stage / Release Boundary

This decision does not claim Stage, QA/Testing, Release Approval, Production, or real provider connectivity.

## Approval Effect

Code is authorized only for BL-041 within the Sprint 11 boundary.
