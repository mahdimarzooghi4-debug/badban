# Badban Domain and Integration Event Contracts

- **Status:** Accepted
- **Date:** 2026-10-05
- **Stage:** Technical
- **Scope:** bounded external-lender pilot
- **Depends on:** Technical Foundation; State Machines; Persistence Model; Policy Runtime Model; API Contracts

## 1. Objective

Define how Badban publishes and consumes domain/integration events without losing ordering, idempotency, causality, or financial correctness.

Core rule:

```
State change is committed locally first
→ event is written to transactional outbox
→ publisher delivers asynchronously
→ consumers process idempotently
```

No financial/business state transition depends on an untracked fire-and-forget message.

## 2. Event Classes

Badban distinguishes four event classes:

1. **Domain Event** — a fact that happened inside Badban.
2. **Integration Event** — a versioned public/internal contract sent to another module/system.
3. **Provider Inbound Event** — an authenticated fact originating from lender/guarantor/custodian/registry.
4. **Operational Event** — telemetry/health signal, not a financial source of truth.

Operational events must never drive financial state transitions directly.

## 3. Standard Event Envelope

Every domain/integration event uses a stable envelope:

```json
{
  "event_id": "uuid",
  "event_type": "GuaranteeReserved",
  "event_version": 1,
  "aggregate_type": "GuaranteeCase",
  "aggregate_id": "uuid",
  "aggregate_version": 4,
  "occurred_at": "2026-10-05T14:30:00+03:30",
  "recorded_at": "2026-10-05T14:30:01+03:30",
  "correlation_id": "uuid",
  "causation_id": "uuid-or-null",
  "policy_pack_id": "uuid-or-null",
  "actor": {
    "type": "USER|SYSTEM|PROVIDER",
    "id": "..."
  },
  "payload": {}
}
```

Rules:

- `event_id` globally unique;
- `event_type + event_version` defines schema;
- aggregate version is the version after the state change;
- timestamps are offset-aware;
- policy reference included when materially relevant.

## 4. Event Immutability

Once emitted, an event is immutable.

Corrections require a new event, for example:

- `ExternalLoanCorrected`;
- `JournalReversed`;
- `ValuationSuperseded`;
- `ReconciliationResolved`.

Consumers must never rely on event deletion or mutation.

## 5. Domain Events

Initial domain event catalog:

### Participant / Program

- `ParticipationEpisodeStarted`
- `ParticipantExitInitiated`
- `ParticipantExitFinalized`

### Asset / Valuation

- `AssetPositionCreated`
- `AssetPositionRestricted`
- `AssetPositionReleased`
- `ValuationAccepted`
- `ValuationMarkedStale`

### Policy

- `PolicyPackReviewed`
- `PolicyPackApproved`
- `PolicyPackActivated`
- `PolicyPackSuperseded`
- `PolicyPackRetired`

### Guarantee

- `GuaranteeRequested`
- `GuaranteeReserved`
- `GuaranteeReservationExpired`
- `GuaranteeIssued`
- `GuaranteeActivated`
- `GuaranteeExposureReduced`
- `GuaranteeReleased`
- `GuaranteeClosed`
- `GuaranteeDelinquent`

### External Loan Mirror

- `ExternalLoanActivated`
- `ExternalLoanRepaymentApplied`
- `ExternalLoanDelinquent`
- `ExternalLoanSettled`
- `ExternalLoanCorrected`

### Claim / Recovery

- `ClaimSubmitted`
- `ClaimApproved`
- `ClaimRejected`
- `ClaimSettlementInitiated`
- `ClaimPaid`
- `RecoveryOpened`
- `RecoveryReceiptRecorded`
- `RecoveryAllocated`
- `RecoveryClosed`

### Risk / Reserve

- `PortfolioRiskEvaluated`
- `PortfolioRiskStateChanged`
- `ReserveDrawRecorded`
- `ReserveReplenished`

### Return / Entitlement

- `ReturnAllocationCalculated`
- `ReturnAllocationApproved`
- `ReturnAllocationPosted`
- `ReturnAllocationReversed`
- `FutureFinancialPaymentRecorded`

### Finance / Reconciliation

- `JournalPosted`
- `JournalReversed`
- `ReconciliationMismatchDetected`
- `ReconciliationResolved`

## 6. Command vs Event

Commands request actions.

Events state facts.

Example:

```
Command: ReserveGuaranteeCapacity
Event:   GuaranteeReserved
```

An event consumer must not interpret an event as permission to bypass the original command preconditions.

## 7. Transactional Outbox Rule

Every integration-relevant domain event is inserted into `outbox_events` in the **same database transaction** as the authoritative aggregate change.

If the local transaction rolls back, the outbox event must not exist.

This guarantees:

```
No committed state without publishable event
```

for workflows requiring integration publication.

## 8. Delivery Semantics

Assume **at-least-once delivery**.

Do not design for exactly-once transport.

Correctness comes from:

- unique event IDs;
- inbox deduplication;
- idempotent consumers;
- aggregate version checks;
- immutable business events.

## 9. Consumer Idempotency

Every consumer persists processed event identity.

Duplicate event delivery must return the previously achieved semantic result and create no second financial/control effect.

For external/provider events, deduplication key is at minimum:

```
(provider_id, event_type, external_event_id)
```

For Badban integration events:

```
event_id
```

is the primary deduplication key.

## 10. Ordering

Global ordering is not assumed.

Ordering is required only where business semantics need it.

Per aggregate, consumers use:

- `aggregate_id`;
- `aggregate_version`.

If an event arrives with version greater than expected + 1:

`EVENT_SEQUENCE_GAP`

The consumer must not guess missing state.

It may:

- defer;
- request/rebuild current state;
- wait for missing event;
- trigger reconciliation.

## 11. Stale Event Handling

If an event arrives with an aggregate version already processed:

- if same `event_id`: duplicate, ignore safely;
- if different event but older aggregate version: classify as stale and do not regress state.

No consumer may move an aggregate backward because an older message arrived late.

## 12. Correlation and Causation

Every workflow must propagate:

- `correlation_id` across the business journey;
- `causation_id` linking the event to the command/event that caused it.

Example:

```
LenderDisbursementReceived
  → GuaranteeActivated
  → BackingEncumbered
  → JournalPosted
```

All should share one correlation chain.

## 13. Provider Inbound Event Envelope

Inbound provider messages are normalized before domain use.

Normalized contract:

```json
{
  "provider_id": "uuid",
  "external_event_id": "string",
  "event_type": "LOAN_DISBURSED",
  "schema_version": 1,
  "external_entity_id": "loan-id",
  "event_time": "2026-10-05T14:30:00+03:30",
  "received_at": "2026-10-05T14:30:05+03:30",
  "payload_hash": "sha256...",
  "evidence_refs": ["..."],
  "payload": {}
}
```

The raw provider payload may be stored separately if policy permits, but domain logic consumes the normalized event.

## 14. Provider Event Authentication

Before an inbound provider event enters the inbox:

1. authenticate provider;
2. validate signature/mTLS/OAuth identity;
3. validate timestamp/nonce where supported;
4. verify provider scope;
5. validate schema;
6. compute/store payload hash;
7. deduplicate external event ID.

Authentication failure must not create a business inbox event.

## 15. Lender Inbound Event Types

Pilot lender adapter must normalize at least:

- `LOAN_APPROVED`
- `LOAN_DISBURSED`
- `REPAYMENT_RECEIVED`
- `LOAN_DELINQUENT`
- `LOAN_SETTLED`
- `LOAN_CORRECTED`

Badban does not infer one event from another when the provider contract defines them separately.

## 16. Guarantee Issuer Inbound Events

Normalize at least:

- `GUARANTEE_ISSUED`
- `GUARANTEE_CANCELLED`
- `GUARANTEE_RELEASED`
- `CLAIM_ACKNOWLEDGED`
- `CLAIM_SETTLEMENT_CONFIRMED`

Legal issuance becomes authoritative only after the expected evidence/verification contract is satisfied.

## 17. Custodian / Collateral Events

Normalize as applicable:

- `ASSET_POSITION_CONFIRMED`
- `COLLATERAL_REGISTERED`
- `COLLATERAL_RELEASED`
- `COLLATERAL_ENFORCED`
- `ASSET_QUANTITY_CORRECTED`

These events feed reconciliation and controlled state transitions.

## 18. Critical Financial Event Rule

The following event types may cause financial/control effects only through an idempotent application command/handler:

- lender repayment;
- loan disbursement;
- claim settlement;
- recovery receipt;
- collateral realization;
- external cash settlement.

Inbound integration handlers must never directly mutate ledger tables.

## 19. Guarantee Activation Event Chain

Expected chain:

```
Provider: LOAN_DISBURSED
→ Inbox accepted
→ Validate guarantee ISSUED
→ Validate amount one-to-one
→ ActivateGuaranteedLoan command
→ GuaranteeActivated
→ ExternalLoanActivated
→ BackingEncumbered
→ Audit/Outbox
```

If amount mismatch:

```
LOAN_GUARANTEE_AMOUNT_MISMATCH
```

No activation event is emitted.

## 20. Repayment Event Chain

```
Provider: REPAYMENT_RECEIVED
→ inbox dedupe
→ ProcessRepayment command
→ ExternalLoanRepaymentApplied
→ if DECLINING:
   GuaranteeExposureReduced
   BackingReleased
→ reconciliation update
```

A duplicate provider event must not reduce exposure twice.

## 21. Claim Event Chain

```
ClaimSubmitted
→ ClaimReviewed
→ ClaimApproved | ClaimRejected
→ if approved:
   ClaimSettlementInitiated
   → external settlement confirmation
   → ClaimPaid
   → RecoveryOpened
```

Claim approval alone does not emit final-loss event.

Final loss occurs only after recovery closure/accounting determination.

## 22. Policy Activation Event

`PolicyPackActivated` must include:

- previous active pack ID if any;
- new pack ID/version;
- scope;
- effective time;
- manifest hash;
- approver;
- impact classification.

Consumers must invalidate scope caches.

Consumers must not rewrite existing transaction snapshots.

## 23. Reconciliation Events

`ReconciliationMismatchDetected` payload should include:

- reconciliation type;
- internal entity/reference;
- external provider/reference;
- materiality;
- mismatch reason code;
- observed values or secure references;
- detected_at.

Sensitive raw evidence should be referenced, not necessarily embedded.

## 24. Event Schema Versioning

Event contracts use explicit `event_version`.

Rules:

- additive optional fields may remain same version;
- breaking semantic/schema changes require a new version;
- consumer compatibility must be tested;
- old versions must remain consumable for the required retention/replay period.

Do not reuse an event type/version with changed meaning.

## 25. Payload Design

Event payloads should contain enough immutable facts for downstream consumers, but not duplicate entire aggregates.

Prefer:

- IDs;
- exact changed business facts;
- policy/version references;
- money/quantity as decimal strings;
- evidence references;
- reason codes.

Avoid:

- secrets;
- large documents;
- unnecessary PII;
- opaque unversioned blobs as the only business content.

## 26. Decimal and Time Rules

All money/quantity fields are decimal strings.

All timestamps are offset-aware ISO 8601/RFC 3339.

No binary float or ambiguous local time in event contracts.

## 27. Event Publication Failure

If local state is committed but broker delivery fails:

- outbox remains unpublished;
- retry with backoff;
- preserve attempt count/error;
- alert on age/backlog threshold.

Do not roll back already committed business state because the broker is temporarily unavailable.

## 28. Dead-Letter Handling

After configured retry limits, an event may enter a dead-letter/exception queue.

Rules:

- original event remains immutable;
- dead-lettering creates operational exception;
- replay is explicit and audited;
- replay uses same event ID unless adapter contract requires a new transport envelope, while preserving original business event identity.

## 29. Replay

Replay must be safe.

Consumers must support reprocessing historical events without duplicate financial effects.

Read-model rebuild may replay domain events.

Financial source-of-truth remains aggregate/journal persistence, not an assumed event-sourcing architecture unless separately approved.

## 30. Event Retention

Retention period is not fixed here, but event/outbox/inbox/audit relationships must preserve traceability for the regulatory/accounting retention period later approved.

## 31. Security Classification

Integration events must be classified by payload sensitivity.

Restricted data must be minimized and, when crossing system boundaries:

- encrypted in transit;
- access controlled;
- omitted from generic logs;
- referenced through evidence IDs where feasible.

## 32. Event Broker Abstraction

Technical architecture may use a broker/queue, but domain contracts must not depend on vendor-specific semantics.

Required logical capabilities:

- durable delivery;
- consumer groups/subscriptions;
- retry handling;
- ordering support at least by aggregate/partition key where needed;
- observability;
- backpressure.

Exact broker selection belongs to deployment/runtime architecture.

## 33. Partition / Ordering Key

For aggregate-oriented events, preferred partition key:

```
aggregate_type + aggregate_id
```

For provider inbound streams requiring lender-loan ordering:

```
provider_id + external_loan_id
```

This does not eliminate version checks.

## 34. Integration Operation State

Long-running outbound integration commands should use explicit operation state:

```
PENDING
→ SENT
→ ACKNOWLEDGED
→ CONFIRMED
```

Failure branches:

- RETRYABLE_FAILED;
- NON_RETRYABLE_FAILED;
- EXPIRED/CANCELLED where applicable.

No external operation is considered successful from HTTP 2xx alone unless provider contract defines that response as authoritative completion.

## 35. Standard Event Errors

Stable processing codes include:

- `EVENT_SCHEMA_INVALID`
- `EVENT_AUTHENTICATION_FAILED`
- `EVENT_DUPLICATE`
- `EVENT_SEQUENCE_GAP`
- `EVENT_STALE`
- `EVENT_SCOPE_INVALID`
- `EVENT_EVIDENCE_INVALID`
- `EVENT_PROCESSING_RETRYABLE`
- `EVENT_PROCESSING_FAILED`

## 36. Test Contract

Every event consumer requires tests for:

- normal processing;
- duplicate delivery;
- out-of-order event;
- sequence gap;
- stale event;
- malformed schema;
- unauthorized provider;
- retry after transient failure;
- crash after state commit but before publish;
- crash after inbox insert but before domain transition;
- replay safety.

Financial event consumers additionally require proof of exactly-once **business effect** under at-least-once delivery.

## 37. Hard Invariants

1. Local authoritative state commits before asynchronous publication.
2. Integration delivery is at-least-once; consumers are idempotent.
3. Duplicate events never duplicate financial effect.
4. Older events never regress aggregate state.
5. Sequence gaps are detected, not guessed through.
6. Provider facts are authenticated before domain processing.
7. Integration handlers do not directly mutate ledger balances.
8. Event schemas are explicitly versioned.
9. Correlation/causation is preserved across workflows.
10. Operational telemetry never becomes financial source of truth.

## 38. Next Technical Contracts

Next:

1. Provider Adapter Contracts;
2. Reconciliation Engine Contract;
3. Identity/RBAC and Maker-Checker Contract;
4. Observability/Deployment/Non-Functional Contracts.
