# Decision 0018 — Technical Stage Complete for Bounded Pilot; Scrum/Product Backlog Authorized

- **Status:** Accepted
- **Date:** 2026-10-05
- **Scope:** Governance / Stage Gate / Initial Technical Architecture
- **Dependencies:** Decision 0017; Technical-Stage Completion Review

## Decision

Badban's Technical stage is complete **for the bounded external-lender pilot scope defined in Decision 0016**.

The project is authorized to move to the next parent-process stage:

```
Technical → Scrum/Product Backlog
```

This authorization does not approve Sprint execution, Code, real-money pilot activation, Release, or Production.

## Accepted Technical Baseline

The bounded pilot uses a **modular transactional core** with:

- one authoritative relational transactional boundary for Badban-owned operational state;
- explicit domain modules and aggregate boundaries;
- local ACID transactions for financial/business invariants;
- append-only ledger/audit/history;
- transactional outbox/inbox for integration reliability;
- versioned policy and deterministic calculators;
- explicit API command/query contracts;
- versioned domain/integration events;
- provider adapter isolation;
- independent reconciliation;
- deny-by-default identity/RBAC;
- maker-checker for high-impact actions;
- security/secret-management boundaries;
- observability and business-readiness controls;
- controlled deployment/runtime and non-functional requirements.

No microservice decomposition is required for the bounded pilot.

## Technical Completion Basis

The Technical-Stage Completion Review found the accepted architecture sufficient to translate into an implementation backlog without inventing unresolved Business behavior.

Accepted Technical contracts cover:

- system/trust boundaries;
- domain aggregates;
- state machines;
- relational persistence and concurrency;
- ledger/posting model;
- policy/versioning;
- APIs;
- events;
- provider adapters;
- reconciliation;
- identity/RBAC/maker-checker;
- security/secrets;
- observability/operations;
- deployment/runtime;
- NFRs;
- testability/recovery requirements.

## Hard Invariants Carried Forward

The Product Backlog and all later implementation must preserve:

1. no guarantee above approved available capacity;
2. no double reservation/encumbrance;
3. external loan principal equals issued guarantee amount;
4. stale/missing valuation cannot create new capacity;
5. no regulated action by an unauthorized legal role;
6. Direct Lending remains disabled for the pilot;
7. no direct financial balance mutation;
8. posted financial journals balance and remain immutable except through reversal/compensating entries;
9. external-dependent financial/legal states require evidence and reconciliation;
10. material financial/risk decisions retain immutable policy/version/algorithm snapshots;
11. duplicate retries/events never create duplicate financial effect;
12. high-impact maker-checker actions cannot be self-approved.

## Backlog Authorization Boundary

Scrum/Product Backlog may now decompose the accepted Technical architecture into:

- epics;
- capabilities;
- user/system stories;
- technical enablers;
- acceptance criteria;
- dependency ordering;
- Definition of Done;
- Sprint-ready slices.

The backlog may also contain concrete implementation-selection work for:

- language/framework;
- relational database product;
- broker/queue;
- identity provider;
- secret/key manager;
- evidence/object storage;
- observability stack;
- deployment platform;
- CI/CD;
- numeric SLO/RPO/RTO;
- approved pilot capacity/load envelope.

Those choices must remain compatible with the accepted Technical contracts.

## Sprint / Code Gate

This decision does **not** authorize Code.

Before Sprint/Code:

- Product Backlog must be created and ordered;
- dependencies and technical enablers must be explicit;
- Sprint scope must be selected;
- acceptance criteria and tests for the selected slice must be defined;
- any implementation technology required by the Sprint must be resolved.

## Production Gate

Real-money activation remains blocked by Decision 0016 and the parent delivery process.

Required later gates include named/validated counterparties, approved numeric Pilot Policy Pack, legal/accounting/provider validation, Stage, QA/Testing, Release Approval, Production readiness, and approved operational targets.

## Consequence

The next repository stage is **Scrum/Product Backlog**.

The parent process is now:

```
Business ✓
→ Technical ✓
→ Scrum/Product Backlog
→ Sprint
→ Code
→ Code Review
→ Stage
→ QA/Testing
→ Release Approval
→ Production
→ Monitoring
→ Improvement
```
