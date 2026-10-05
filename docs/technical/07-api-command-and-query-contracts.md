# Badban API Command and Query Contracts

- **Status:** Proposed
- **Date:** 2026-10-05
- **Stage:** Technical
- **Scope:** bounded external-lender pilot
- **Depends on:** Technical Foundation; State Machines; Relational Data Model; Policy Runtime Model

## 1. API Objective

Badban APIs must expose explicit business commands and read models without allowing clients to mutate financial state directly.

The API contract must preserve:

- authorization;
- aggregate versioning;
- idempotency;
- policy resolution;
- stable error codes;
- evidence references;
- auditability;
- separation of commands from queries.

## 2. API Style

The pilot API shall use versioned HTTP/JSON endpoints under:

```
/api/v1
```

Command endpoints represent business actions rather than generic CRUD updates.

Avoid generic endpoints such as:

```
PATCH /guarantees/{id} { "state": "ACTIVE" }
```

Instead use explicit commands such as:

```
POST /api/v1/guarantees/{id}/activate
```

with required evidence and expected aggregate version.

## 3. Common Request Headers

State-changing commands should support:

- `Authorization: Bearer <token>`
- `Idempotency-Key: <opaque-key>`
- `If-Match: "<aggregate-version>"` or equivalent explicit `expected_version`
- `X-Correlation-Id` optional client-provided correlation ID

Provider callbacks use provider-specific authentication rather than participant/operator bearer tokens.

## 4. Common Command Envelope

Command bodies should include only business inputs, not server-owned fields.

Common logical fields:

```json
{
  "effective_at": "2026-10-05T10:00:00Z",
  "reason_code": "OPTIONAL_REASON",
  "evidence_refs": ["..."],
  "policy_pack_id": "optional-explicit-id-when-required"
}
```

The server remains authoritative for:

- actor identity;
- policy compatibility;
- current aggregate state;
- calculation output;
- journal IDs;
- audit IDs;
- resulting aggregate version.

## 5. Common Command Response

Successful command:

```json
{
  "data": {
    "id": "aggregate-id",
    "state": "RESERVED",
    "version": 4
  },
  "meta": {
    "correlation_id": "corr-id",
    "audit_event_id": "audit-id",
    "decision_snapshot_id": "snapshot-id"
  }
}
```

A command response may include relevant journal/outbox references when created.

## 6. Error Contract

All domain/API errors use a stable envelope:

```json
{
  "error": {
    "code": "VALUATION_STALE",
    "message": "Human-readable localized message",
    "details": {},
    "correlation_id": "corr-id"
  }
}
```

The `code` is the stable machine contract.

The human-readable message may be localized and is not used for business branching.

## 7. HTTP Status Mapping

Recommended mapping:

- `400` malformed/structurally invalid request;
- `401` unauthenticated;
- `403` authenticated but unauthorized;
- `404` resource not found in authorized scope;
- `409` aggregate version conflict, idempotency conflict, invalid state transition, business concurrency conflict;
- `422` valid request shape but business rule rejection;
- `429` rate limiting;
- `503` authoritative dependency/policy resolution unavailable when fail-closed;
- `500` unexpected internal failure.

Financial/business rejection must not be returned as a false success.

## 8. Idempotency Contract

Every repeatable state-changing endpoint must support `Idempotency-Key`.

Server behavior:

1. first request stores request hash and business result;
2. same key + same request returns same semantic result;
3. same key + different request returns `IDEMPOTENCY_CONFLICT`;
4. duplicate request must not duplicate financial/control effects.

Provider inbound events are deduplicated by provider-scoped external event ID in addition to command idempotency.

## 9. Optimistic Concurrency Contract

State-changing commands require expected aggregate version where concurrent mutation is possible.

On mismatch:

```
409 AGGREGATE_VERSION_CONFLICT
```

Response may include current version metadata, but the server must not silently overwrite.

## 10. Pagination and Query Conventions

Collection queries use cursor pagination:

- `limit`;
- `cursor`;
- deterministic sort.

Response:

```json
{
  "data": [],
  "page": {
    "next_cursor": "..."
  }
}
```

Offset pagination should not be relied on for high-volume append-only financial/event streams.

## 11. Participation APIs

### Query participant episode

```
GET /api/v1/participation-episodes/{id}
```

Returns:

- program;
- support status;
- consent state;
- exit status summary;
- authorized participant-facing references.

### Initiate exit

```
POST /api/v1/participation-episodes/{id}/exit
```

Requires:

- expected version;
- authorized actor;
- reason/evidence where required.

Does not imply financial closure.

## 12. Asset Position APIs

### Create Asset Position

```
POST /api/v1/asset-positions
```

Input includes:

- participation/program context;
- Asset Type;
- ownership/funding type;
- legal owner reference;
- custodian reference;
- quantity;
- source evidence.

The API must not accept client-supplied guarantee capacity.

### Query Asset Position

```
GET /api/v1/asset-positions/{id}
```

Returns current write-state plus latest authorized read-model summary.

### List participant positions

```
GET /api/v1/participation-episodes/{id}/asset-positions
```

## 13. Valuation APIs

### Ingest valuation

Internal/provider command:

```
POST /api/v1/asset-positions/{id}/valuations
```

Requires approved source identity/evidence.

Accepted valuation is immutable.

### Query valuation history

```
GET /api/v1/asset-positions/{id}/valuations
```

### Query current valuation summary

```
GET /api/v1/asset-positions/{id}/valuation-summary
```

Returns freshness explicitly.

## 14. Guarantee Capacity Query

```
GET /api/v1/participation-episodes/{id}/guarantee-capacity
```

This is a deterministic read model based on:

- eligible Asset Positions;
- latest accepted valuations;
- policy pack;
- existing reservations/exposure;
- portfolio controls.

Response must include:

- gross backing capacity;
- reserved capacity;
- active exposure;
- other holds;
- available guarantee capacity;
- valuation timestamp/freshness;
- policy pack/version;
- calculation timestamp;
- calculation/algorithm version.

A read calculation does not reserve capacity.

## 15. Create Guarantee Request

```
POST /api/v1/guarantees
```

Input:

- participation episode;
- provider;
- credit product version/product reference;
- requested principal.

Creates `REQUESTED`.

No capacity is consumed until reservation command succeeds.

## 16. Reserve Guarantee Capacity

```
POST /api/v1/guarantees/{id}/reserve
```

Requires:

- expected version;
- idempotency key;
- ACTIVE Pilot Policy Pack;
- fresh valuation;
- participant capacity;
- portfolio risk PASS;
- provider/product/legal authorization valid.

Response includes:

- reserved amount;
- reservation expiry;
- backing allocation references;
- policy/decision snapshot;
- resulting state/version.

Business failures include:

- `POLICY_PACK_NOT_ACTIVE`;
- `VALUATION_STALE`;
- `CAPACITY_INSUFFICIENT`;
- `PORTFOLIO_RISK_RED`;
- `PROVIDER_NOT_ACTIVE`;
- `AUTHORIZATION_INVALID`.

## 17. Confirm Legal Guarantee Issuance

```
POST /api/v1/guarantees/{id}/confirm-issuance
```

This is an internal/authorized operation, not a participant action.

Input includes:

- legal Guarantee Issuer;
- external guarantee identifier;
- issued amount;
- evidence reference;
- issuance timestamp.

Requires:

- state RESERVED;
- reservation valid;
- issuer authorization VALID;
- issued amount consistent with approved reservation/amendment.

Moves to `ISSUED`.

## 18. Activate Guaranteed Loan

```
POST /api/v1/guarantees/{id}/activate
```

Normally triggered from verified lender disbursement evidence or controlled operations workflow.

Input includes:

- external loan ID;
- disbursed principal;
- disbursement timestamp;
- evidence reference.

Hard validation:

```
disbursed_principal = issued_guarantee_amount
```

Mismatch returns:

`LOAN_GUARANTEE_AMOUNT_MISMATCH`

No partial activation.

## 19. Guarantee Workspace Query

```
GET /api/v1/guarantees/{id}/workspace
```

Returns one operational read model containing:

- guarantee state;
- participant/program;
- provider/product;
- requested/reserved/issued/current exposure;
- backing allocations;
- valuation/policy snapshots;
- legal guarantee reference;
- external loan mirror;
- reconciliation status;
- claim/recovery summary;
- blockers/actions allowed for current actor.

The query must not expose secret provider credentials or unrelated participant data.

## 20. Lender Event Ingestion

Provider-scoped endpoint:

```
POST /api/v1/integrations/lenders/{provider_id}/events
```

Examples:

- LOAN_APPROVED;
- LOAN_DISBURSED;
- REPAYMENT_RECEIVED;
- LOAN_DELINQUENT;
- LOAN_SETTLED;
- LOAN_CORRECTED.

Requirements:

- provider authentication;
- external event ID;
- event timestamp;
- evidence/payload integrity;
- inbox deduplication.

Inbound acceptance does not necessarily mean business transition completed.

Response should distinguish:

- accepted for processing;
- duplicate;
- rejected authentication/schema.

## 21. External Loan Query

```
GET /api/v1/external-loans/{id}
```

Returns mirrored authoritative lender state and reconciliation freshness.

It must clearly identify lender as lender of record.

## 22. Claim APIs

### Submit/register claim

```
POST /api/v1/guarantees/{id}/claims
```

Authorized lender integration or controlled operations command.

Input:

- lender claim reference;
- requested amount;
- evidence refs.

### Start/complete validation

Internal workflow endpoints may use explicit commands such as:

```
POST /api/v1/claims/{id}/review
POST /api/v1/claims/{id}/approve
POST /api/v1/claims/{id}/reject
```

Approval requires expected version, authorized approver, reconciliation, and eligible amount.

### Settle approved claim

```
POST /api/v1/claims/{id}/settle
```

Requires:

- approved state;
- settlement source;
- amount;
- payment evidence/reference according to settlement state machine.

## 23. Recovery APIs

```
GET /api/v1/recoveries/{id}
POST /api/v1/recoveries/{id}/receipts
POST /api/v1/recoveries/{id}/allocate
POST /api/v1/recoveries/{id}/close
```

Each recovery receipt is idempotent.

Closing requires final allocation/reconciliation.

## 24. Risk APIs

### Current portfolio risk

```
GET /api/v1/risk/portfolio
```

Returns:

- GREEN/AMBER/RED;
- exposure metrics;
- reserve metrics;
- concentration summary;
- snapshot timestamp;
- policy version.

### Re-evaluate risk

Privileged/internal:

```
POST /api/v1/risk/portfolio/evaluate
```

Creates immutable risk snapshot.

No participant can call this endpoint.

## 25. Policy APIs

### Query policy packs

```
GET /api/v1/admin/policy-packs
GET /api/v1/admin/policy-packs/{id}
```

### Create draft

```
POST /api/v1/admin/policy-packs
```

### Review / approve / activate

```
POST /api/v1/admin/policy-packs/{id}/review
POST /api/v1/admin/policy-packs/{id}/approve
POST /api/v1/admin/policy-packs/{id}/activate
POST /api/v1/admin/policy-packs/{id}/retire
```

Approval and activation are separate.

Policy activation is high-impact and subject to maker/checker/RBAC.

## 26. Provider and Authorization APIs

```
GET /api/v1/admin/providers
POST /api/v1/admin/providers
GET /api/v1/admin/providers/{id}
POST /api/v1/admin/providers/{id}/activate
POST /api/v1/admin/providers/{id}/suspend
```

Legal authorization:

```
GET /api/v1/admin/legal-entities/{id}/authorizations
POST /api/v1/admin/legal-entities/{id}/authorizations
POST /api/v1/admin/authorizations/{id}/verify
POST /api/v1/admin/authorizations/{id}/suspend
```

No activation may infer authorization.

## 27. Reconciliation APIs

### Queue

```
GET /api/v1/reconciliation/cases
```

Filters:

- type;
- status;
- materiality;
- provider;
- age.

### Case

```
GET /api/v1/reconciliation/cases/{id}
```

### Resolve

```
POST /api/v1/reconciliation/cases/{id}/resolve
```

Requires:

- authorized actor;
- reason;
- resolution evidence;
- maker/checker where policy requires.

Original mismatch evidence remains visible.

## 28. Ledger APIs

Ledger APIs are privileged/read-mostly.

### Query journal

```
GET /api/v1/finance/journals/{id}
GET /api/v1/finance/journals
```

### Reverse journal

```
POST /api/v1/finance/journals/{id}/reverse
```

Requires:

- authorized finance actor;
- reason;
- expected conditions;
- maker/checker if required.

No API exists for arbitrary balance update.

## 29. Return Allocation APIs

```
POST /api/v1/return-allocations
POST /api/v1/return-allocations/{id}/calculate
POST /api/v1/return-allocations/{id}/approve
POST /api/v1/return-allocations/{id}/post
POST /api/v1/return-allocations/{id}/reverse
```

Posting requires balanced allocation and valid recognized source return.

## 30. Future Financial APIs

```
GET /api/v1/participation-episodes/{id}/future-financial
POST /api/v1/future-financial/{id}/payments
```

Payment requires vested payable balance and settlement workflow.

## 31. Exit APIs

```
POST /api/v1/participation-episodes/{id}/exit
GET /api/v1/exit-cases/{id}
GET /api/v1/exit-cases/{id}/statement
POST /api/v1/exit-cases/{id}/reconcile
POST /api/v1/exit-cases/{id}/finalize
```

Finalize must fail when mandatory unresolved items remain.

## 32. Participant-Facing Summary

```
GET /api/v1/me/badban-summary
```

or equivalent participant-scoped endpoint.

May include:

- participant-owned vs program-attributed asset summary;
- current valuation summary;
- available/encumbered backing;
- guarantee amount/status;
- lender identity;
- external loan outstanding;
- entitlement balances;
- releasable/restricted status.

Must not expose internal risk secrets or unrelated records.

## 33. Audit APIs

Privileged read-only:

```
GET /api/v1/audit/events
GET /api/v1/audit/aggregates/{type}/{id}
```

Filters must preserve authorization scope.

Audit events are never edited through API.

## 34. Command Authorization Contract

Every command passes:

```
authentication
→ RBAC
→ resource/program scope
→ legal-role/provider scope
→ maker/checker requirement
→ business preconditions
→ policy gate
```

Authorization success does not imply business-rule success.

## 35. Read Authorization Contract

Queries must enforce:

- participant self-scope;
- program/entity scope for staff;
- least privilege;
- field-level suppression where necessary.

A `404` may be preferable to revealing existence of an unauthorized sensitive resource.

## 36. API Versioning

Breaking contract changes require a new API version or explicit compatibility strategy.

Internal schema evolution must not silently change meaning of stable API fields/reason codes.

New optional response fields may be additive.

## 37. Money and Quantity Encoding

All monetary and precision-sensitive numeric values should be serialized as decimal strings, for example:

```json
{
  "amount": "12500000.00",
  "quantity": "10.500000"
}
```

Clients must not rely on binary floating-point representation.

Currency/unit fields are explicit.

## 38. Timestamp Encoding

Use RFC 3339 / ISO 8601 offset-aware timestamps.

No ambiguous local time.

Example:

```
2026-10-05T14:30:00+03:30
```

## 39. Long-Running Commands

Commands that depend on external providers may return a pending operation reference:

```json
{
  "data": {
    "operation_id": "...",
    "status": "PENDING"
  }
}
```

Query:

```
GET /api/v1/operations/{id}
```

Pending must not be presented as completed.

## 40. Stable Domain Errors

In addition to policy errors, the API must support stable codes including:

- `AGGREGATE_VERSION_CONFLICT`;
- `IDEMPOTENCY_CONFLICT`;
- `INVALID_STATE_TRANSITION`;
- `VALUATION_STALE`;
- `CAPACITY_INSUFFICIENT`;
- `PORTFOLIO_RISK_RED`;
- `PROVIDER_NOT_ACTIVE`;
- `AUTHORIZATION_INVALID`;
- `RESERVATION_EXPIRED`;
- `LOAN_GUARANTEE_AMOUNT_MISMATCH`;
- `RECONCILIATION_BLOCK`;
- `CLAIM_NOT_ELIGIBLE`;
- `LEDGER_POSTING_FAILED`;
- `MAKER_CHECKER_REQUIRED`;
- `EXTERNAL_EVIDENCE_REQUIRED`;
- `EXTERNAL_STATE_STALE`.

## 41. No Generic Admin Override Endpoint

There must be no endpoint like:

```
POST /api/v1/admin/force-state
```

Exceptional operations must still use domain-specific commands with explicit authorization, reason, evidence, and audit.

## 42. OpenAPI Requirement

Implementation should generate/maintain an OpenAPI contract for all HTTP endpoints.

The OpenAPI contract must include:

- schemas;
- auth requirements;
- idempotency requirements;
- version headers/fields;
- stable error responses;
- decimal-string formats;
- endpoint role descriptions.

OpenAPI is not the source of business rules by itself; it must remain consistent with the accepted Technical contracts.

## 43. Test Contract

Every command endpoint requires tests for:

- success path;
- unauthorized actor;
- invalid state;
- version conflict;
- duplicate idempotency key;
- stale/missing external evidence where relevant;
- policy failure;
- domain invariant failure;
- retry safety.

Financial commands additionally require proof that failed requests leave no partial ledger/control effects.

## 44. Next Technical Contracts

Next:

1. domain and integration event contracts;
2. provider adapter contracts;
3. reconciliation engine contract;
4. identity/RBAC and maker-checker contract;
5. observability/deployment/non-functional contracts.
