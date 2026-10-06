# Decision 0031 — Sprint 07 Guarantee Request Aggregate; Code Authorization

- **Status:** Accepted
- **Date:** 2026-10-06
- **Scope:** Sprint 07 / Code Authorization / Bounded External-Lender Pilot
- **Depends on:** Decision 0023; Sprint 06 Code Review Complete; Technical 02, 03, 04, 07, 11

## Decision

Accept Sprint 07 and authorize Code only for:

- **BL-019 — Guarantee Request Aggregate Path**

## Request Is Intent, Not Reservation

`POST /api/v1/guarantees` creates a GuaranteeCase in:

```
REQUESTED
```

It records a request intent only.

Request creation does not:

- reserve capacity;
- create backing allocation;
- create exposure;
- perform portfolio risk evaluation;
- issue a legal guarantee;
- activate an external loan;
- post ledger entries;
- call an external provider.

## Policy Pack Clarification for REQUESTED

For the REQUESTED state, implementation may persist:

```
policy_pack_id = NULL
```

This resolves the lifecycle timing between Technical 04 and Technical 06/07:

- Technical 07 §15 does not provide a policy input for request creation;
- Technical 03 gates ACTIVE policy at `REQUESTED → RESERVED`;
- Technical 06 §9 captures the authoritative policy snapshot at reservation.

Therefore Sprint 07 must not resolve an implicit latest policy or guess a policy pack during request creation.

The exact policy pack is captured only by a future separately authorized reservation command.

## GuaranteeCase Creation Contract

The request must preserve:

- participation episode;
- provider;
- exact credit product version;
- requested principal;
- product-derived guarantee mode;
- state `REQUESTED`;
- aggregate version and audit metadata.

Future lifecycle fields remain empty until their authorized commands occur.

Current guarantee exposure is zero because REQUESTED creates no exposure.

## Product Coherence

Request creation must validate:

- product version exists;
- product belongs to the selected provider;
- requested principal is positive exact Decimal;
- requested principal is within the selected product version's explicit min/max bounds.

No production numeric value is introduced by this decision; validation uses the already stored product version.

Provider/product ACTIVE state and legal authorization remain reservation gates as defined by Technical 03.

## API and Idempotency

Authorized API:

```
POST /api/v1/guarantees
```

It must:

- require authentication and scoped authorization;
- require `Idempotency-Key`;
- create at most one semantic GuaranteeCase for the same key+payload;
- reject changed payload reuse;
- return REQUESTED state and aggregate version.

No generic state mutation endpoint is authorized.

## Authorization

The existing command permission matrix permits `OPERATIONS` to submit a guarantee request within authorized scope.

This decision does not add participant self-service creation.

Auditor remains read-only.

## No Invented Domain Event

Technical 08 currently does not define a GuaranteeRequested event.

Sprint 07 must not invent a new integration/domain event merely to create REQUESTED.

Creation must still be auditable using existing audit infrastructure.

## No Financial/Control Effect

The command must produce no:

- BackingAllocation;
- asset capacity lock change;
- DecisionSnapshot;
- risk snapshot;
- reservation expiry;
- guarantee exposure;
- journal posting;
- external provider call;
- legal issuance;
- external loan;
- claim/recovery;
- cash movement.

## Explicitly Unauthorized

This decision does not authorize:

- BL-016;
- BL-020;
- BL-021;
- BL-022 through BL-026;
- BL-030;
- BL-032;
- new BL-041 behavior;
- capacity reservation/release;
- policy capture at REQUESTED;
- provider/lender/Guarantee Issuer integrations;
- Direct Lending;
- Stage;
- QA/Testing gate completion;
- Release Approval;
- Production;
- real-money use.

## Definition-of-Done Gate

Sprint 07 must satisfy the Accepted Sprint 07 plan, including:

- exact Decimal and referential-integrity tests;
- provider/product coherence tests;
- product min/max validation;
- idempotency tests;
- authorization tests;
- no-side-effect tests;
- `policy_pack_id IS NULL` proof for REQUESTED;
- full CI gates;
- Code Review complete.

## Stage Boundary

Decision 0023 remains in force.

Sprint 07 may be implemented and reviewed while Stage is unavailable, but reviewed output only accumulates into the future Stage candidate.

## Approval Effect

This decision is Accepted.

Code is authorized only for BL-019 within the boundaries above.
