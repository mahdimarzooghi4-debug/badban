# Badban Technical

- **Stage:** Technical
- **Entry Gate:** Authorized by Decision 0017
- **Scope:** bounded external-lender pilot defined by Decision 0016

## Parent delivery process

**Business → Technical → Scrum/Product Backlog → Sprint → Code → Code Review → Stage → QA/Testing → Release Approval → Production → Monitoring → Improvement**

The Business stage is complete for Technical entry only within the bounded pilot scope.

Real-money activation remains separately gated.

## Technical documents

- [00 — Technical Foundation](./00-technical-foundation.md) — **Accepted**
- [01 — System Context and Trust Boundaries](./01-system-context-and-trust-boundaries.md) — **Accepted**
- [02 — Domain Aggregate Boundaries](./02-domain-aggregate-boundaries.md) — **Accepted**
- [03 — State Machines and Transition Contracts](./03-state-machines-and-transition-contracts.md) — **Accepted**
- [04 — Relational Data Model and Persistence Constraints](./04-relational-data-model-and-persistence-constraints.md) — **Proposed**

## Binding inputs

Technical design must comply with Accepted decisions in [../decisions](../decisions/README.md), especially Decisions 0008–0017.

## Scope guard

Badban Direct Lending is outside the initial pilot and must not be implemented as an implicit requirement.

Any future direct-lending architecture must wait for its Business/legal gates.
