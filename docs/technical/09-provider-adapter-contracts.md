# Badban Provider Adapter Contracts

- **Status:** Accepted
- **Date:** 2026-10-05
- **Stage:** Technical
- **Scope:** bounded external-lender pilot
- **Depends on:** Technical Foundation; API Contracts; Event Contracts; System Context; Decision 0014

## 1. Objective

Define how Badban integrates with external regulated providers without leaking provider-specific semantics into the domain core.

The adapter boundary must isolate:

- transport;
- authentication;
- provider schema;
- retry behavior;
- polling/webhook behavior;
- error mapping;
- evidence capture;
- reconciliation.

Core rule:

```
Badban Domain Contract
↕
Provider Adapter
↕
Provider-Specific API / File / Portal / Manual Process
```

The domain must not depend directly on a provider's proprietary payloads or transient transport behavior.

## 2. Provider Classes in Pilot

The bounded pilot may integrate with:

1. External Lender;
2. Guarantee Issuer;
3. Custodian / Asset Provider;
4. Collateral Registry;
5. Settlement / Banking Rail where required;
6. Valuation / Market Data Provider where external valuation is used.

The initial pilot has one active lender and one active Guarantee Issuer, but the adapter model remains generic.

## 3. Adapter Capability Contract

Each adapter exposes an explicit capability manifest.

Example logical capabilities:

- supports_push_events;
- supports_polling;
- supports_command_submission;
- supports_batch_file;
- supports_manual_confirmation;
- supports_mtls;
- supports_signed_messages;
- supports_idempotency_key;
- supports_event_sequence;
- supports_reconciliation_snapshot.

Badban must not assume every provider supports the same transport or callback mode.

## 4. Integration Modes

Supported logical modes:

### API

Synchronous request/response and/or asynchronous status workflow.

### Webhook / Callback

Provider pushes authenticated event to Badban.

### Polling

Badban queries provider for authoritative state.

### Secure Batch / File

Structured file exchanged through approved secure channel.

### Controlled Manual

Used only where no reliable system integration exists.

Manual confirmation must preserve actor, evidence, timestamp, maker/checker when required, and audit trail.

No mode may bypass domain invariants.

## 5. Adapter Interface

Every provider adapter should expose a normalized internal interface such as:

- submit_command(command);
- fetch_state(reference);
- fetch_reconciliation_snapshot(scope);
- verify_inbound_message(raw_request);
- normalize_inbound_event(raw_payload);
- translate_error(provider_error);
- health_check();
- capability_manifest();

Provider-specific SDK/client code remains behind this interface.

## 6. Outbound Command Envelope

Normalized outbound command should contain:

- command_id;
- provider_id;
- operation_type;
- external/business reference;
- idempotency key;
- correlation ID;
- effective timestamp where relevant;
- normalized payload;
- evidence references where required.

The adapter translates this into provider-specific wire format.

The domain never constructs provider-specific request JSON directly.

## 7. Inbound Normalization

Provider payloads must be normalized into the accepted Provider Inbound Event envelope from Technical 08.

Normalization must:

- preserve original external identifiers;
- convert money/quantity to decimal strings;
- normalize timestamp format;
- map provider-specific status/code to Badban canonical code;
- attach payload hash/evidence reference;
- preserve unknown provider data only as controlled extension/evidence, not as domain state.

## 8. Authentication

Adapter configuration must support provider-specific authentication without exposing secrets to domain code.

Possible methods include:

- mTLS;
- OAuth2 client credentials;
- signed HTTP requests;
- HMAC/signature verification;
- provider API key in secret manager;
- SFTP/managed secure file channel;
- network allowlist where appropriate.

Secrets are retrieved by secret reference, not copied into provider database rows.

## 9. Secret Handling

Provider credentials must:

- live in approved secret storage;
- be environment-specific;
- never appear in API responses;
- never appear in logs;
- support rotation;
- be scoped to least privilege.

Credential rotation must not alter historical financial records or provider IDs.

## 10. Request Timeout Policy

Every remote call must have explicit:

- connect timeout;
- request timeout;
- overall operation timeout where applicable.

No unbounded remote call is allowed.

Timeout does not mean failure of the provider-side business action.

A timed-out command enters an uncertain/pending state until retried safely or reconciled.

## 11. Retry Classification

Provider errors are classified into:

### RETRYABLE

Examples:

- timeout;
- connection failure;
- provider temporary unavailable;
- HTTP 429;
- provider 5xx when provider contract says retryable.

### NON_RETRYABLE

Examples:

- authentication invalid;
- schema rejected;
- business rule rejection;
- unknown product;
- invalid external reference.

### UNKNOWN_OUTCOME

Example:

- request timed out after provider may have accepted it.

UNKNOWN_OUTCOME must not be blindly retried without provider idempotency or status lookup.

## 12. Retry Policy

Retries use:

- bounded exponential backoff;
- jitter where implementation supports it;
- attempt counter;
- next attempt timestamp;
- maximum retry budget.

High-impact operations require provider-safe idempotency before automated retry.

If provider has no idempotency capability, retry strategy must prefer status lookup/reconciliation over duplicate command submission.

## 13. Circuit Breaker

Adapters should implement circuit-breaker behavior for repeated transport/provider failure.

States:

```
CLOSED
→ OPEN
→ HALF_OPEN
→ CLOSED
```

An OPEN circuit blocks new non-essential remote calls for the configured recovery window.

Circuit breaker affects availability, not authoritative business state.

The system must not mark a financial action successful because the circuit is open.

## 14. Bulkhead / Isolation

Failure of one provider adapter must not exhaust resources required by another provider or core financial processing.

At minimum, isolate:

- connection pools;
- worker queues;
- retry queues;
- circuit-breaker state;
- credentials;
- metrics.

## 15. Provider Error Translation

Provider-specific errors are translated to normalized integration errors.

Examples:

- PROVIDER_AUTHENTICATION_FAILED;
- PROVIDER_TIMEOUT;
- PROVIDER_RATE_LIMITED;
- PROVIDER_UNAVAILABLE;
- PROVIDER_SCHEMA_REJECTED;
- PROVIDER_BUSINESS_REJECTED;
- PROVIDER_REFERENCE_NOT_FOUND;
- PROVIDER_DUPLICATE_REQUEST;
- PROVIDER_OUTCOME_UNKNOWN;
- PROVIDER_CONTRACT_MISMATCH.

Raw provider messages may be retained as evidence but must not become stable API reason codes.

## 16. Correlation Mapping

Each outbound operation must store:

- Badban command/operation ID;
- correlation ID;
- provider request ID if returned;
- provider entity ID;
- external status/reference;
- attempt history.

This enables tracing from Badban transaction to provider evidence.

## 17. Integration Operation State

Outbound provider operations use:

```
PENDING
→ SENT
→ ACKNOWLEDGED
→ CONFIRMED
```

Failure branches:

- RETRYABLE_FAILED;
- NON_RETRYABLE_FAILED;
- UNKNOWN_OUTCOME;
- EXPIRED;
- CANCELLED where valid.

HTTP success is not necessarily CONFIRMED.

Provider contract must define which response/event constitutes authoritative completion.

## 18. Lender Adapter Contract

The lender adapter should support, as applicable:

### Outbound

- submit application/reference;
- query loan decision;
- query loan state;
- query repayment state;
- request reconciliation snapshot.

### Inbound / normalized events

- LOAN_APPROVED;
- LOAN_DISBURSED;
- REPAYMENT_RECEIVED;
- LOAN_DELINQUENT;
- LOAN_SETTLED;
- LOAN_CORRECTED.

### Required authoritative fields

At minimum:

- provider/lender ID;
- external loan ID;
- original principal;
- disbursed principal;
- outstanding principal;
- currency;
- event time;
- repayment reference;
- delinquency state when applicable.

### Hard activation rule

The adapter may report disbursement, but only the domain command can activate the guarantee after verifying:

```
External Loan Principal = Issued Guarantee Amount
```

## 19. Guarantee Issuer Adapter Contract

The Guarantee Issuer adapter should support:

### Outbound

- submit guarantee issuance request where provider permits;
- query issuance status;
- query guarantee state;
- submit/track claim where contract permits;
- fetch reconciliation snapshot.

### Inbound

- GUARANTEE_ISSUED;
- GUARANTEE_CANCELLED;
- GUARANTEE_RELEASED;
- CLAIM_ACKNOWLEDGED;
- CLAIM_SETTLEMENT_CONFIRMED.

### Required authoritative fields

- guarantee issuer ID;
- external guarantee ID;
- issued amount;
- beneficiary/lender reference;
- issue date;
- state;
- claim/settlement references where applicable;
- evidence reference.

Badban must never treat an internal reservation as equivalent to legal guarantee issuance.

## 20. Custodian / Asset Provider Adapter

Supports authoritative evidence for:

- asset position confirmation;
- quantity/balance;
- custody account/reference;
- encumbrance if provider manages it;
- release;
- enforcement/realization if applicable.

Normalized events may include:

- ASSET_POSITION_CONFIRMED;
- ASSET_QUANTITY_CORRECTED;
- ASSET_RESTRICTED;
- ASSET_RELEASED;
- ASSET_REALIZED.

Badban AssetPosition remains its operational model, but externally held quantity/control must reconcile to the provider.

## 21. Collateral Registry Adapter

Where legal registration is required, adapter supports:

- register collateral;
- query registration;
- query encumbrance;
- release registration;
- fetch evidence/document reference;
- reconciliation snapshot.

Normalized events:

- COLLATERAL_REGISTERED;
- COLLATERAL_RELEASED;
- COLLATERAL_ENFORCED;
- COLLATERAL_REGISTRATION_CORRECTED.

No internal-only encumbrance may be represented as legally registered if provider confirmation is absent.

## 22. Settlement / Banking Rail Adapter

Where Badban-controlled settlement occurs, adapter supports:

- submit payment instruction;
- query payment status;
- receive settlement confirmation;
- fetch reconciliation statement/snapshot.

Normalized events:

- PAYMENT_ACCEPTED;
- PAYMENT_SETTLED;
- PAYMENT_REJECTED;
- PAYMENT_REVERSED;
- PAYMENT_CORRECTED.

Badban marks real cash movement completed only from authoritative settlement evidence.

## 23. Valuation Provider Adapter

Where valuation is external, adapter supports:

- fetch latest observation;
- optionally receive price/value event;
- identify source timestamp;
- provide source reference/evidence.

The adapter must not itself calculate guarantee capacity.

It only supplies authoritative valuation inputs.

## 24. Mapping Layer

Provider-specific statuses map into canonical Badban concepts.

Example:

```
Provider "paid_out"
Provider "funded"
Provider "disbursed"
→ LOAN_DISBURSED
```

Mappings must be versioned per provider adapter.

A mapping change must not reinterpret already processed historical provider events.

## 25. Schema Versioning

Each adapter maintains:

- provider contract version;
- Badban adapter mapping version;
- inbound normalization version;
- outbound request mapping version.

These versions are captured in integration-operation/evidence records.

## 26. Provider Contract Drift

Adapters must detect unexpected provider behavior such as:

- unknown status code;
- missing required field;
- changed decimal precision;
- changed signature scheme;
- changed schema version.

Unexpected contract drift returns:

`PROVIDER_CONTRACT_MISMATCH`

and fails closed for high-impact financial transitions.

## 27. Polling Strategy

Polling is allowed when webhook/events are absent or insufficient.

Polling requirements:

- configurable interval;
- provider rate-limit awareness;
- cursor/watermark where supported;
- last successful poll timestamp;
- lag metric;
- idempotent normalization.

Polling must never use current state to erase unprocessed historical provider events where those events matter.

## 28. Webhook Strategy

Webhook endpoint must:

1. authenticate;
2. validate size/schema;
3. persist inbox/evidence;
4. respond quickly;
5. process asynchronously.

Long-running financial processing must not occur inline before webhook acknowledgment.

## 29. File / Batch Strategy

Secure batch import must preserve:

- file ID;
- provider ID;
- schema version;
- checksum/hash;
- received timestamp;
- row/event identity;
- row-level processing result;
- rejection reason;
- reprocessing history.

Duplicate files/rows must not duplicate financial effects.

## 30. Manual Adapter Mode

For providers without system integration, a controlled manual adapter may expose operations like:

- record provider confirmation;
- attach evidence;
- record external reference;
- initiate reconciliation.

Manual adapter rules:

- only authorized staff;
- evidence mandatory;
- maker/checker for high-impact confirmations;
- reason code mandatory;
- no direct state override;
- same domain command path as automated adapters.

## 31. Provider Capability Registry

Store provider capabilities as configuration, including:

- integration mode;
- supported commands;
- supported inbound events;
- authentication method;
- polling availability;
- webhook availability;
- reconciliation snapshot support;
- idempotency support;
- rate-limit policy reference.

Domain code asks capability registry instead of hard-coding provider name checks.

## 32. Adapter Health

Each adapter reports operational health:

- AVAILABLE;
- DEGRADED;
- UNAVAILABLE;
- AUTH_FAILURE;
- CONTRACT_MISMATCH.

Health is operational, not financial truth.

A degraded adapter may block unsafe new actions according to policy but must not rewrite existing obligation states.

## 33. Reconciliation Requirement

Every provider adapter must support a reconciliation path even if event integration is perfect.

Minimum reconciliation capability:

- fetch authoritative current state or statement;
- identify provider snapshot timestamp;
- preserve source evidence/reference;
- compare against Badban mirror/control state.

Events provide timeliness; reconciliation provides independent control.

## 34. Provider Suspension

If provider becomes SUSPENDED/EXPIRED:

- block new regulated exposure;
- continue servicing/reconciliation of existing obligations;
- preserve adapter read/reconciliation capability where legally/operationally possible;
- do not delete credentials/history until retention/transition requirements are satisfied.

## 35. Data Minimization

Adapters exchange only data necessary for provider role.

Do not send unrelated participant information.

Provider-specific PII/financial payloads must be excluded from generic application logs.

## 36. Observability

Adapter metrics should include:

- request rate;
- success/failure rate;
- p50/p95/p99 latency;
- timeout count;
- retry count;
- circuit state;
- auth failures;
- schema/contract mismatches;
- inbound lag;
- reconciliation lag;
- pending/unknown-outcome operations.

## 37. Test Contract

Every adapter requires contract tests for:

- authentication success/failure;
- happy-path mapping;
- unknown provider status;
- malformed payload;
- duplicate inbound event;
- timeout;
- retryable failure;
- non-retryable business rejection;
- unknown outcome;
- rate limit;
- webhook signature failure;
- schema-version drift;
- idempotent retry;
- reconciliation snapshot mapping.

High-impact adapters require sandbox/stub integration tests before production activation.

## 38. Provider Certification Gate

Before a provider becomes ACTIVE in Badban:

- adapter contract implemented;
- authentication verified;
- error mapping verified;
- idempotency behavior tested;
- reconciliation path tested;
- evidence references verified;
- timeout/retry behavior tested;
- operational contacts/escalation defined;
- legal authorization already VALID under Decision 0014.

Technical readiness alone does not activate the provider.

## 39. Hard Invariants

1. Provider-specific payloads never enter domain logic unnormalized.
2. Provider secrets remain outside domain/database records.
3. Remote timeout never implies success or failure by itself.
4. UNKNOWN_OUTCOME is explicit.
5. Retries never duplicate financial effects.
6. Manual integrations use the same domain invariants as automated integrations.
7. Internal reservation is never equivalent to external legal issuance.
8. Internal cash journal is never equivalent to external settlement without evidence.
9. Provider contract drift fails closed for high-impact actions.
10. Every provider has an independent reconciliation path.

## 40. Next Technical Contracts

Next:

1. Reconciliation Engine Contract;
2. Identity/RBAC and Maker-Checker Contract;
3. Observability, Deployment, and Non-Functional Contracts.
