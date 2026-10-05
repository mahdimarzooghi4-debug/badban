# Badban Technical Foundation

- **Status:** Proposed
- **Date:** 2026-10-05
- **Stage:** Technical
- **Scope:** bounded external-lender pilot
- **Business Gate:** Decision 0017
- **Production Gate:** Decision 0016 activation requirements remain mandatory

## 1. Technical Objective

Build a system that can execute the accepted Badban pilot business chain with deterministic financial controls, auditable state transitions, provider reconciliation, and explicit legal-role boundaries.

The architecture must optimize first for:

1. correctness;
2. traceability;
3. financial consistency;
4. idempotency;
5. recoverability;
6. policy/version reproducibility;
7. operational simplicity for the bounded pilot.

Scale and distributed decomposition are secondary to correctness at this stage.

## 2. Proposed Architecture Style

For the initial pilot, Badban should begin as a **modular transactional core** with clearly separated domain modules, one authoritative transactional data store for Badban-owned operational state, and asynchronous integration at external boundaries.

Conceptually:

```
Clients / Operations UI
        ↓
Badban Application API
        ↓
Modular Domain Core
        ├─ Participant / Program
        ├─ Asset / Ownership
        ├─ Valuation
        ├─ Policy / Capacity
        ├─ Guarantee
        ├─ Credit Provider / Product
        ├─ External Loan Mirror
        ├─ Risk / Reserve
        ├─ Claims / Recovery
        ├─ Return Allocation
        ├─ Exit / Entitlement
        ├─ Ledger
        ├─ Reconciliation
        ├─ Legal Entity / Authorization
        └─ Audit
        ↓
Transactional Database
        ↓
Outbox / Integration Workers
        ↓
External Providers / Registries
```

The pilot should avoid splitting these domains into independent distributed services before transaction boundaries and operational load justify it.

## 3. Authoritative-State Rule

Badban must explicitly classify every important field/state as one of:

- **Badban authoritative**;
- **external-provider authoritative, mirrored in Badban**;
- **derived from immutable inputs and policy**;
- **reconciled state**.

Examples:

### Badban authoritative

- Asset Type policy;
- Asset Position ownership/funding classification;
- guarantee capacity;
- reservation;
- guarantee internal lifecycle;
- risk state;
- policy-pack version;
- entitlement allocation;
- Badban ledger;
- exit state.

### External authoritative / mirrored

- lender credit approval;
- external loan identifier;
- lender disbursement;
- lender repayment receipts;
- lender outstanding principal;
- custodian position evidence;
- legal guarantee issuance evidence;
- external collateral registration.

Badban must never silently replace an external authoritative fact with an inferred value.

## 4. Domain Modules

### 4.1 Participant and Program

Owns:

- Participant;
- Participation Episode;
- Program;
- enrollment/eligibility reference;
- consent/disclosure state;
- support-program status.

Must not own financial balances directly.

### 4.2 Asset Registry and Position

Owns:

- Asset Type;
- Asset Position;
- quantity/unit;
- ownership/funding type;
- legal owner;
- custodian reference;
- availability/restriction state.

Must not calculate guarantee capacity by itself.

### 4.3 Valuation

Owns immutable valuation observations:

- price/value;
- source;
- timestamp;
- currency;
- FX reference where relevant;
- policy version;
- freshness state.

Missing/stale valuation cannot create new capacity.

### 4.4 Policy and Versioning

Owns versioned policy artifacts including:

- Asset Type policy;
- ownership/funding policy;
- provider/product policy;
- risk policy;
- return-allocation policy;
- Pilot Policy Pack.

Every material financial decision must retain its effective policy version.

### 4.5 Guarantee Capacity

Deterministically derives capacity from:

- eligible Asset Positions;
- pledgeability;
- valuation;
- Advance Rate;
- concentration/portfolio controls;
- existing reservations/exposure/holds.

No random, heuristic, or opaque AI decisioning is permitted in the capacity calculation.

### 4.6 Guarantee Lifecycle

Owns:

- request;
- reservation;
- issuance synchronization;
- activation;
- exposure;
- release;
- delinquency linkage;
- claim linkage;
- closure.

Hard invariant:

```
External Loan Principal = Issued Badban Guarantee Amount
```

### 4.7 Provider and Credit Product Registry

Owns:

- provider identity;
- legal role/status;
- product definition;
- product limits;
- repayment/tenor/fee rules;
- delinquency/claim rules;
- integration mode.

No provider-specific rule should be hard-coded outside policy/adapters unless it is a true domain invariant.

### 4.8 External Loan Mirror

Stores lender-reported state with:

- external loan ID;
- original principal;
- outstanding principal;
- schedule/reference;
- disbursement status;
- repayment history;
- delinquency;
- synchronization timestamp;
- reconciliation state.

It is not a Badban direct-loan receivable.

### 4.9 Risk and Reserve

Owns:

- portfolio exposure;
- concentration metrics;
- reserve requirements;
- reserve availability references;
- GREEN / AMBER / RED state;
- stop-issuance gate;
- stress-test results.

Participant capacity PASS cannot override portfolio RED.

### 4.10 Claim and Recovery

Owns:

- claim submission;
- validation;
- approval/rejection;
- settlement;
- recovery;
- enforcement;
- surplus/shortfall resolution.

Claim payment, recovered cash, and final economic loss remain separate facts.

### 4.11 Return Allocation and Entitlement

Owns:

- eligible return input;
- reserve contribution;
- livelihood;
- future financial;
- capital growth;
- social reinvestment;
- participant/program entitlement status.

Principal and return must never be conflated.

### 4.12 Exit

Owns participant financial transition:

- EXIT_ELIGIBLE;
- EXIT_INITIATED;
- FINANCIAL_RECONCILIATION;
- obligations/transition-support states;
- FINALIZED.

Program exit does not automatically release active collateral.

### 4.13 Financial Ledger

Owns append-only journals and balanced postings.

Rules:

- no direct balance mutation;
- every monetary journal balances;
- corrections use reversal/compensating postings;
- event and posting IDs are immutable;
- sub-ledger dimensions preserve economic/legal ownership.

### 4.14 Reconciliation

Owns comparison jobs and exceptions for:

- custody;
- lender;
- guarantee issuer;
- bank/settlement;
- collateral registry.

States:

- MATCHED;
- PENDING;
- MISMATCH;
- STALE;
- DISPUTED.

Critical mismatch may block issuance, release, claim settlement, or exit finalization.

### 4.15 Legal Entity and Authorization

Owns:

- legal entity;
- legal role;
- regulator/authority;
- authorization/license;
- scope;
- validity period;
- status;
- evidence.

A regulated action must fail closed when required authorization is invalid.

### 4.16 Audit

Every material command/state transition must retain:

- actor/system;
- timestamp;
- previous state;
- new state;
- reason;
- source evidence;
- correlation/causation identifiers;
- policy version.

## 5. Transaction Boundaries

The pilot architecture should favor local ACID transactions for Badban-owned invariants.

Examples that should be atomic inside Badban:

### Guarantee Reservation

```
validate valuation
+ validate participant capacity
+ validate portfolio gate
+ reserve backing
+ create reservation
+ write ledger/audit events
```

### Guarantee Activation

```
validate legal issuance evidence
+ validate lender disbursement evidence
+ validate one-to-one amount
+ activate guarantee
+ activate exposure
+ encumber backing
+ update external-loan mirror
+ write ledger/audit events
```

### Capacity Release

```
validate authoritative repayment/closure
+ reduce/release exposure
+ release corresponding backing
+ update ledger
+ write audit
```

External calls must not be assumed atomic with the local transaction.

## 6. External Integration Pattern

External providers are integrated through adapters.

Each adapter should support:

- command submission where permitted;
- inbound state ingestion;
- signature/authentication validation;
- idempotency;
- retries;
- timeout handling;
- duplicate suppression;
- evidence/reference persistence;
- reconciliation.

Preferred processing model:

```
Local Transaction
→ Transactional Outbox
→ Integration Worker
→ External Provider
→ Provider Response / Callback / Poll
→ Inbox / Deduplication
→ Local State Transition
```

No critical financial state should depend on an untracked fire-and-forget call.

## 7. Idempotency

Every externally repeatable command/event must have an idempotency boundary.

Examples:

- create reservation;
- issue guarantee request;
- ingest lender disbursement;
- ingest repayment;
- submit/settle claim;
- post recovery;
- post allocation;
- release collateral.

Duplicate delivery must produce the same business result, not a duplicate financial effect.

## 8. Concurrency Safety

Capacity and collateral operations require concurrency control.

The system must prevent:

- two simultaneous reservations consuming the same capacity;
- release racing with claim creation;
- revaluation racing with issuance without a consistent snapshot;
- duplicate repayment reducing exposure twice;
- duplicate claim settlement.

Implementation may use row/version locking or another proven concurrency mechanism, but the invariant is mandatory.

## 9. State-Machine Discipline

Each major lifecycle must use explicit allowed transitions.

No arbitrary status string update is permitted.

Every transition should define:

- source states;
- target state;
- authorization;
- preconditions;
- side effects;
- ledger effects;
- audit event;
- reconciliation requirements.

## 10. Policy Snapshot

Material transactions must capture immutable references to their effective policies.

A later policy change affects future decisions unless an accepted contract explicitly provides otherwise.

Historical calculation/review must be reproducible without reading today's policy as if it existed in the past.

## 11. Financial Precision

The system must not use binary floating point for financial values.

Technical design must define:

- decimal precision per currency;
- asset-quantity precision per Asset Type;
- deterministic rounding;
- allocation residual policy;
- comparison tolerances only where explicitly appropriate.

No silent rounding may break the one-to-one loan/guarantee invariant.

## 12. Time Semantics

Every external and internal event should distinguish:

- event/effective time;
- received time;
- processed time;
- reconciliation time.

Business deadlines such as reservation expiry, valuation freshness, delinquency thresholds, and license expiry must use explicit timezone-aware timestamps.

## 13. Identity and Authorization

Technical architecture must support least-privilege roles for at least:

- participant;
- operations user;
- risk user;
- finance/reconciliation user;
- legal/compliance user;
- provider integration identity;
- admin/governance approver;
- auditor/read-only reviewer.

High-impact actions should support maker/checker where required by policy.

## 14. Evidence Model

A critical external state must be traceable to evidence.

Examples:

- custody statement/reference;
- valuation source;
- legal guarantee identifier;
- lender approval;
- disbursement confirmation;
- repayment receipt;
- collateral registration;
- claim evidence;
- settlement transaction.

Evidence metadata must be immutable even if external documents are stored outside the core database.

## 15. Security Boundary

The design must protect:

- participant identity;
- financial balances;
- legal documents;
- provider credentials;
- signing/authorization secrets;
- audit history.

Provider credentials must never be stored in ordinary application records or logs.

Security architecture details are a Technical follow-up, but no design may require secrets to be exposed to clients.

## 16. Observability

Every critical flow should emit structured operational telemetry correlated by business IDs.

At minimum:

- reservation latency/failure;
- guarantee issuance sync;
- lender sync freshness;
- reconciliation mismatch count/age;
- ledger-posting failures;
- outbox backlog;
- provider error rates;
- risk-state changes;
- stale valuation count;
- blocked transaction reasons.

Monitoring must distinguish operational failure from legitimate business rejection.

## 17. Failure Policy

Financial workflows must fail closed when a required authoritative fact is missing or stale.

Examples:

- stale valuation → block new capacity;
- provider license invalid → block new regulated action;
- lender state stale beyond policy → block affected release/claim decision as configured;
- ledger posting failure → business transaction fails/rolls back;
- critical reconciliation mismatch → configured business gate blocks.

Availability must not override financial correctness.

## 18. Pilot Scope Exclusions

The Technical pilot must not implement as active production behavior:

- Badban Direct Lending;
- multi-lender simultaneous operation;
- multiple production Asset Types;
- multi-currency accounting;
- generalized cross-collateralization;
- autonomous AI credit decisions;
- automatic asset enforcement without authorized control.

Code may preserve extensibility, but inactive features must not create hidden production paths.

## 19. Technical Deliverables Before Scrum

Before moving to Scrum/Product Backlog, Technical must produce and approve:

1. system context and trust boundaries;
2. domain model / aggregate boundaries;
3. lifecycle/state-machine specifications;
4. relational/data model;
5. ledger/posting model;
6. policy/versioning model;
7. API contracts;
8. event contracts;
9. provider-adapter contracts;
10. reconciliation model;
11. identity/RBAC model;
12. security/secrets model;
13. observability model;
14. deployment/runtime topology;
15. failure/retry/idempotency rules;
16. non-functional requirements;
17. test strategy for financial invariants.

## 20. Technical Definition of Done

The Technical stage is complete when the above architecture/contracts are explicit enough that Scrum items can be created without inventing unresolved domain behavior during implementation.

Technical completion does not mean production activation.
