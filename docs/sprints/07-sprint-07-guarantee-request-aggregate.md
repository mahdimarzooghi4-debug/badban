# Sprint 07 — Guarantee Request Aggregate Path

- **Status:** Completed through Code Review; Merged to main
- **Date:** 2026-10-06
- **Stage:** Deferred by Decision 0023
- **Scope:** bounded external-lender pilot
- **Entry Gate:** Decision 0023; Sprint 06 Code + Code Review Complete
- **Depends on:** BL-009, BL-017, BL-018 complete through Code Review
- **Code Authorization:** GRANTED BY DECISION 0031

## 1. Sprint Goal

Deliver only the first non-financial GuaranteeCase command:

- **BL-019 — Guarantee Request Aggregate Path**

The Sprint creates an explicit, idempotent `REQUESTED` intent record with exact participant/provider/product/principal references.

It does not reserve capacity, create exposure, issue a guarantee, call a provider, or move money.

## 2. Why BL-019 Is the Next Ready Capability

BL-019 is now dependency-ready because:

- ParticipationEpisode foundation exists;
- provider/product registry is complete through Code Review;
- legal entity/authorization registry is complete through Code Review.

BL-019 is intentionally smaller than BL-020 and introduces no financial/control side effect.

## 3. BL-016 Remains Deferred

BL-016 — Guarantee Capacity Read Model remains deferred by Decision 0030.

Its accepted contract requires authoritative:

- reserved capacity;
- active exposure;
- other approved holds;
- portfolio controls.

Those sources still do not exist. Sprint 07 must not synthesize zero/default values for them.

## 4. GuaranteeCase REQUESTED Contract

Sprint 07 may introduce the `GuaranteeCase` persistence foundation required by Technical 04.

For the `REQUESTED` state, the record must preserve at least:

- guarantee case ID;
- participation episode ID;
- provider ID;
- exact credit product version ID;
- state = `REQUESTED`;
- requested principal as exact Decimal;
- guarantee mode copied from the selected product version;
- aggregate version;
- created/updated timestamps.

Server-owned future fields remain unset until their authorized lifecycle commands occur:

- reserved guarantee amount;
- issued guarantee amount;
- reservation expiry;
- legal guarantee external ID;
- legal guarantee issuer;
- external loan mirror reference;
- risk snapshot;
- closure timestamp.

`current_guarantee_exposure` is zero while the case is only REQUESTED because no exposure exists yet.

## 5. Policy Pack Clarification

Sprint 07 does **not** resolve or capture an ACTIVE Pilot Policy Pack when creating a REQUESTED case.

The implementation contract for REQUESTED is:

```
policy_pack_id = NULL
```

Rationale:

- Technical 07 §15 Create Guarantee Request does not take a policy pack input;
- Technical 03 places the ACTIVE Pilot Policy Pack gate on `REQUESTED → RESERVED`;
- Technical 06 §9 captures the authoritative policy snapshot when the case becomes RESERVED;
- request creation does not yet have the full reservation context needed for deterministic policy resolution.

Therefore:

- no implicit `latest` policy lookup is allowed;
- no arbitrary policy pack may be guessed;
- reservation will later populate/capture the exact policy under a separately authorized Sprint.

This is a deliberate implementation clarification for the REQUESTED state only.

## 6. Request Validation Boundary

Creating a request validates only what is necessary to create a coherent intent record:

- participation episode reference exists;
- provider reference exists;
- credit product version reference exists;
- selected product version belongs to the selected provider;
- requested principal is exact Decimal and greater than zero;
- requested principal is within the explicit min/max principal bounds of the selected product version;
- guarantee mode is copied from the selected product version, never client-invented.

Request creation does **not** perform reservation gates.

The following remain future `REQUESTED → RESERVED` checks:

- participant/program eligibility for reservation;
- ACTIVE Pilot Policy Pack;
- fresh authoritative valuation;
- capacity sufficiency;
- portfolio risk PASS;
- provider/product ACTIVE;
- legal authorization validity;
- backing availability/concurrency.

A REQUESTED record must never be represented as approved, reserved, issued, active, or legally authorized merely because it exists.

## 7. API Surface

Sprint 07 may implement only the accepted Technical 07 §15 command:

```
POST /api/v1/guarantees
```

Business input:

- participation episode ID;
- provider ID;
- credit product version ID;
- requested principal.

Server-owned fields are not accepted from the client.

The response returns the created GuaranteeCase identity, `REQUESTED` state, and aggregate version using the existing API command conventions.

No generic GuaranteeCase PATCH/CRUD mutation API is authorized.

## 8. Idempotency and Concurrency

`POST /api/v1/guarantees` must require `Idempotency-Key`.

Rules:

- first request creates one GuaranteeCase;
- same key + same payload returns the same semantic result;
- same key + different payload returns idempotency conflict;
- retry never creates a duplicate GuaranteeCase.

Creation starts at aggregate version 1.

No expected aggregate version is needed for creating a new aggregate; later state-changing commands must be version-aware.

## 9. Authorization

Sprint 07 uses the existing deny-by-default RBAC engine.

The accepted operational command permission is:

- `OPERATIONS` may submit a guarantee request within its authorized participation/program/resource scope.

Sprint 07 does not create a participant self-service guarantee-request permission.

Auditor remains read-only.

No route name or UI state substitutes for server-side authorization.

## 10. Audit and History

Guarantee request creation is audited with:

- actor identity/type;
- correlation ID;
- GuaranteeCase ID;
- participation/provider/product references;
- resulting aggregate version;
- success/failure outcome as supported by existing audit conventions.

Sprint 07 does not invent a new domain event type when none is accepted by Technical 08.

No synthetic state-transition row with a made-up `from_state` is required for aggregate creation.

Future accepted state transitions will append to `guarantee_state_history`.

## 11. Explicit No-Side-Effect Boundary

Creating REQUESTED must not:

- calculate or consume capacity;
- create/update capacity locks;
- create BackingAllocation;
- create DecisionSnapshot;
- create PortfolioRiskSnapshot;
- create reservation expiry;
- create guarantee exposure;
- create legal guarantee evidence;
- create ExternalLoanMirror;
- post journal entries;
- call provider/lender/Guarantee Issuer systems;
- create claims/recovery;
- move money.

## 12. Acceptance Tests

Tests must prove at least:

- valid request creates exactly one `REQUESTED` GuaranteeCase;
- requested principal uses exact Decimal;
- provider and product version references are explicit;
- product must belong to the selected provider;
- principal below product minimum or above product maximum is rejected;
- guarantee mode comes from the exact product version;
- `policy_pack_id` remains NULL in REQUESTED;
- reserved/issued amounts and reservation/risk/legal/external-loan references remain unset;
- current guarantee exposure is zero;
- idempotent replay returns the same semantic result;
- idempotency-key reuse with changed payload fails;
- unauthorized actor fails with no GuaranteeCase side effect;
- auditor cannot create;
- no BackingAllocation, DecisionSnapshot, journal, capacity-lock, provider-call, or financial side effect occurs;
- migration drift and full CI gates remain green.

## 13. Definition of Done

Sprint 07 Code is Done through Code Review only when:

- BL-019 is implemented within the accepted REQUESTED-only boundary;
- persistence follows Technical 04 referential integrity and exact Decimal rules;
- accepted POST endpoint is implemented;
- authorization and idempotency are proven;
- no reservation or downstream workflow is introduced;
- full format/lint/type/migration/test/security/dependency/container CI gates are green;
- Code Review completes.

Stage remains Deferred under Decision 0023.

## 14. Explicit Non-Goals

Sprint 07 does not implement:

- BL-016 Guarantee Capacity Read Model;
- BL-020 Atomic Backing Reservation;
- BL-021 Reservation Expiry;
- BL-022/023 Guarantee Issuer path;
- BL-024/025/026 lender/loan activation path;
- BL-030 ledger work;
- BL-032 portfolio risk gate;
- BL-041 new event/outbox behavior beyond existing infrastructure;
- BackingAllocation;
- capacity locks;
- DecisionSnapshot for request creation;
- provider network calls;
- legal guarantee issuance;
- claims/recovery;
- Direct Lending;
- production provider/product/policy values;
- Stage;
- QA/Testing gate completion;
- Release Approval;
- Production;
- real-money use.

## 15. Approval Effect

This Sprint 07 plan is Accepted.

Decision 0031 grants Code authorization only for BL-019 under the boundaries above.


## 16. Completion Record

Sprint 07 completed its authorized Code and Code Review scope for BL-019.

- Pull Request: #8 — `Sprint 07: guarantee request aggregate path`
- Reviewed head: `f4b1f51cfdbe9fd6698f22836564b23ede29f473`
- Reviewed-head CI: Run #193 — SUCCESS
- Merge commit on `main`: `9dd8dbd1a3c7771356e43e7dbd3254866911baf6`
- Merge-commit CI: Run #194 — SUCCESS
- BL-019: Code + Code Review complete
- Stage: Deferred under Decision 0023
- QA/Testing gate completion: not claimed
- Release Approval: not claimed
- Production / real-money use: not authorized

Review hardening included:

- GuaranteeCase creation remains REQUESTED-only;
- `policy_pack_id` remains NULL at REQUESTED;
- requested principal is encoded as a decimal string and validated against the `NUMERIC(38,18)` storage boundary;
- response monetary values remain decimal strings;
- product/provider coherence and product min/max bounds are enforced;
- provider/product ACTIVE state, legal authorization, valuation, risk, capacity, and backing checks remain reservation gates;
- authorization is scoped to the ParticipationEpisode program;
- auditor remains read-only;
- idempotency is race-safe for concurrent first-time retries and changed-payload reuse remains rejected;
- request creation is audited without inventing a new GuaranteeRequested event;
- no BackingAllocation, DecisionSnapshot, capacity reservation, risk evaluation, journal posting, provider call, legal issuance, external loan, or guarantee exposure is created.

No BL-016, BL-020, BL-021, BL-022 through BL-026, BL-030, BL-032, capacity reservation/release, policy capture at REQUESTED, provider/lender/Guarantee Issuer integration, Direct Lending, Stage, QA gate completion, Release Approval, Production, or real-money behavior is authorized by this completion record.
