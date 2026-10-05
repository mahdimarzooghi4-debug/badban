# Badban Technical

- **Stage:** Technical Complete for Bounded Pilot — Scrum/Product Backlog Authorized
- **Entry Gate:** Authorized by Decision 0017
- **Exit Gate:** Decision 0018
- **Scope:** bounded external-lender pilot defined by Decision 0016

## Parent delivery process

**Business → Technical → Scrum/Product Backlog → Sprint → Code → Code Review → Stage → QA/Testing → Release Approval → Production → Monitoring → Improvement**

The Technical stage is complete for translation into Scrum/Product Backlog within the bounded pilot scope.

This does not authorize Sprint execution, Code, real-money activation, Release, or Production.

## Technical documents

- [00 — Technical Foundation](./00-technical-foundation.md) — **Accepted**
- [01 — System Context and Trust Boundaries](./01-system-context-and-trust-boundaries.md) — **Accepted**
- [02 — Domain Aggregate Boundaries](./02-domain-aggregate-boundaries.md) — **Accepted**
- [03 — State Machines and Transition Contracts](./03-state-machines-and-transition-contracts.md) — **Accepted**
- [04 — Relational Data Model and Persistence Constraints](./04-relational-data-model-and-persistence-constraints.md) — **Accepted**
- [05 — Ledger Account Taxonomy and Posting Templates](./05-ledger-account-taxonomy-and-posting-templates.md) — **Accepted**
- [06 — Policy and Versioning Runtime Model](./06-policy-and-versioning-runtime-model.md) — **Accepted**
- [07 — API Command and Query Contracts](./07-api-command-and-query-contracts.md) — **Accepted**
- [08 — Domain and Integration Event Contracts](./08-domain-and-integration-event-contracts.md) — **Accepted**
- [09 — Provider Adapter Contracts](./09-provider-adapter-contracts.md) — **Accepted**
- [10 — Reconciliation Engine Contract](./10-reconciliation-engine-contract.md) — **Accepted**
- [11 — Identity, RBAC, and Maker-Checker Contract](./11-identity-rbac-and-maker-checker-contract.md) — **Accepted**
- [12 — Security and Secrets Contract](./12-security-and-secrets-contract.md) — **Accepted**
- [13 — Observability and Operational Readiness Contract](./13-observability-and-operational-readiness-contract.md) — **Accepted**
- [14 — Deployment, Runtime Topology, and Non-Functional Requirements](./14-deployment-runtime-topology-and-non-functional-requirements.md) — **Accepted**
- [15 — Technical-Stage Completion Review](./15-technical-stage-completion-review.md) — **PASS / Accepted**

## Binding inputs

Technical design and all later implementation must comply with Accepted decisions in [../decisions](../decisions/README.md), especially Decisions 0008–0018.

## Scope guard

Badban Direct Lending is outside the initial pilot and must not be implemented as an implicit requirement.

Any future direct-lending architecture must wait for its Business/legal gates.

## Next stage

The next repository stage is **Scrum/Product Backlog**.

Backlog decomposition must preserve traceability to these accepted Technical contracts and must not authorize Code before Sprint scope, acceptance criteria, tests, dependencies, and required implementation selections are explicit.
