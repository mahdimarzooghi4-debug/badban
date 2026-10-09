# Sprint 32 — Integration Delivery Operations (BL-041)

- **Date:** 2026-10-09
- **Status:** Code package, exact-SHA CI and automated Technical Code Review pending
- **Base:** Sprint 31 PR #34, exact-head CI #452 SUCCESS
- **Scope:** Backend-only governed operational inspection of existing transactional Outbox/Inbox

## Accepted implementation contract

Five read-only API endpoints under `/api/v1/integration-delivery`:

1. `GET /outbox`: bounded, exact event type/aggregate type/correlation/status filters.
2. `GET /outbox/{message_id}`: exact delivery metadata.
3. `GET /inbox`: bounded exact authenticated source/event type/status filters.
4. `GET /inbox/{message_id}`: exact inbox processing metadata.
5. `GET /summary`: observed Outbox states QUEUED/RETRY_SCHEDULED/DEAD_LETTERED/PUBLISHED and Inbox PENDING/PROCESSED.

All require an **actual active GLOBAL** grant for human AUDITOR or SYSTEM_OPERATOR; Program-only, operations-only, revoked and service identities fail closed. Lists sort by persisted time + ID and require a cursor anchor in the same filtered stream. Default 50, max 100. Status is derived from persisted delivery lifecycle and one observation timestamp; no invented age/alert cutoff or health PASS.

Response is an allowlist of delivery metadata only: no Outbox/Inbox payload, payload digest, free-text dead-letter reason, last-error message, provider body, secrets, or evidence content. Read requests do not retry, dead-letter, replay, acknowledge, settle, reserve, alter GuaranteeCase, mutate Journal, or trigger remote provider calls. Existing internal explicit dead-letter and replay service methods are **not** exposed as new API actions.

## Acceptance evidence

- PostgreSQL integration tests for all five endpoints, status summary, complete pagination, cross-filter/cross-source cursor failure, correlation/status filtering, minimal payload, 401/403/404, revoked and human-vs-service identity enforcement.
- OpenAPI declarations prove GET-only API and metadata-only response fields.
- No new DB migrations, background worker behavior or business controls. Tests and full CI are required.

## Deferred

BL-020 contracts, actual provider credentials, integration transport certification, production alert thresholds, broker delivery assertions and finance transitions remain deferred. This package reports persisted facts only. No Merge, Stage/QA, Release, Production or Figma.
