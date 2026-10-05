# Badban Deployment, Runtime Topology, and Non-Functional Requirements

- **Status:** Accepted
- **Date:** 2026-10-05
- **Stage:** Technical
- **Scope:** bounded external-lender pilot
- **Depends on:** Technical Foundation; Security Contract; Observability Contract; Provider Adapter Contracts; Reconciliation Contract

## 1. Objective

Define the deployable runtime shape and non-functional requirements required to operate Badban safely for the bounded external-lender pilot.

The architecture must preserve the already accepted Technical rule:

```
correctness
> financial consistency
> recoverability
> auditability
> operational simplicity
> scale complexity
```

The bounded pilot must not introduce distributed complexity unless a concrete Technical requirement justifies it.

## 2. Runtime Architecture Style

The pilot runtime remains a **modular transactional core**.

Logical components may be separately deployable processes where operationally useful, but they remain one coherent product architecture with one authoritative transactional data boundary for Badban-owned operational state.

The initial topology should prefer:

- one application/API deployment unit;
- one authoritative relational database;
- separate background worker processes where useful;
- transactional outbox/inbox;
- provider adapters;
- evidence/object storage;
- identity provider;
- secret/key management;
- observability stack.

No microservice split is required for the pilot.

## 3. Logical Runtime Topology

```
Users / Participant / Staff
            |
            v
      Public Edge / WAF
            |
            v
      Web / API Runtime
            |
            v
  Modular Transactional Core
   |        |        |
   |        |        +--> Read Models
   |        |
   |        +--> Transactional DB
   |               |
   |               +--> Outbox
   |               +--> Inbox
   |               +--> Journal / Audit
   |
   +--> Background Workers
           |
           +--> Provider Adapters
           +--> Reconciliation Jobs
           +--> Projection Jobs
           +--> Expiry / Scheduled Commands
                   |
                   v
          External Providers
       Lender / Guarantor /
       Custodian / Registry /
       Settlement / Valuation

Supporting services:
- Identity Provider
- Secret / Key Manager
- Evidence Object Storage
- Broker / Queue if selected
- Metrics / Logs / Traces
```

## 4. Process Separation

The following may run as separate process types even when built from one codebase:

### API Runtime

Responsibilities:

- HTTP API;
- authentication/authorization;
- synchronous domain commands;
- synchronous queries;
- transaction initiation;
- read-model delivery.

### Integration Worker

Responsibilities:

- publish outbox events;
- send provider commands;
- process retries;
- poll provider state;
- process provider callbacks after inbox acceptance.

### Reconciliation Worker

Responsibilities:

- scheduled/on-demand reconciliation;
- comparison;
- mismatch creation;
- reconciliation block updates.

### Projection Worker

Responsibilities:

- rebuild/update derived read models;
- maintain query-oriented projections;
- never become financial source of truth.

### Scheduler / Time-Driven Command Worker

Responsibilities:

- reservation expiry;
- scheduled reconciliation;
- policy-effective actions only when explicit lifecycle rules permit;
- stale-state detection;
- operational reminders.

Time passing must result in explicit idempotent commands, not direct DB mutation.

## 5. Database Topology

The initial pilot should use one authoritative relational database cluster/instance for Badban-owned transactional state.

It must support:

- ACID transactions;
- row-level concurrency control or equivalent;
- foreign keys;
- exact decimal/numeric types;
- timezone-aware timestamps;
- reliable indexing;
- append-only history protection;
- backup/restore;
- transactionally consistent outbox/inbox writes.

Financial invariants must not depend on eventual consistency between multiple authoritative databases in the pilot.

## 6. Database Ownership Rule

Only trusted Badban runtime identities and controlled migration/administration identities may connect to the transactional database.

External providers, web browsers, and client applications never connect directly.

Read-only reporting access, if introduced, must not bypass application authorization or expose restricted data without a separately approved control path.

## 7. Broker / Queue

A broker/queue may be used for asynchronous integration and worker decoupling.

Required logical properties:

- durable messages;
- retry capability;
- consumer isolation;
- ordering/partition support where needed;
- observability;
- backpressure.

The architecture remains correct if a broker is temporarily unavailable because the transactional outbox retains unpublished work.

Broker transport is not the financial source of truth.

## 8. Evidence Storage

Large legal/financial documents and provider evidence may be stored in object storage.

The transactional database stores immutable evidence metadata/references.

Evidence storage requires:

- encryption;
- access control;
- versioning or immutability where appropriate;
- integrity hash;
- lifecycle/retention controls;
- non-public access.

## 9. Identity Runtime

Human authentication should be delegated to a centralized identity provider.

The Badban application consumes validated identity claims and enforces current server-side authorization/grants.

The identity provider must not become the only source of dynamic fine-grained authorization truth.

## 10. Secret / Key Runtime

Applications obtain secrets from a secret/key management system.

Runtime containers/processes receive only needed secret references/values.

No build artifact contains production secrets.

Key/secret manager unavailability must fail closed for new operations that require unavailable secrets.

## 11. Environment Model

Minimum environments:

- Development;
- Test/CI;
- Stage;
- Production.

Each environment has separate:

- database;
- provider credentials;
- signing/encryption keys;
- storage;
- identity clients;
- broker/queue namespaces;
- secrets;
- telemetry namespaces.

Stage should resemble Production closely enough to validate deployment, migrations, provider stubs/sandbox, observability, and recovery behavior.

## 12. Stage Purpose

Stage is the controlled pre-production environment for:

- full workflow validation;
- schema migrations;
- provider adapter certification;
- integration tests;
- security tests;
- operational readiness;
- reconciliation tests;
- backup/restore rehearsal;
- production-like monitoring.

Stage must not be presented as Production and must not accidentally use live production credentials unless an explicit approved integration test exception exists.

## 13. Deployment Units

The pilot should keep deployable units small in number.

Recommended logical units:

1. Web/API;
2. Worker runtime;
3. optional scheduled/reconciliation worker;
4. relational database;
5. identity provider integration;
6. object storage;
7. secret/key service;
8. broker/queue if selected;
9. observability services.

Workers may share code/artifact with API runtime while using different startup roles.

## 14. Stateless Application Rule

Web/API and worker processes should remain stateless between requests/jobs except for controlled local caches.

Authoritative state must live in approved persistent stores.

This enables:

- safe restart;
- horizontal replication when needed;
- deterministic recovery;
- simpler deployment.

## 15. Horizontal Scaling

Horizontal scaling is allowed for:

- API instances;
- integration workers;
- projection workers;
- reconciliation workers where work can be partitioned safely.

Scaling must preserve:

- idempotency;
- row-level/aggregate concurrency rules;
- provider rate limits;
- event ordering requirements;
- maker-checker correctness;
- transaction isolation.

Scaling must not introduce duplicate financial effects.

## 16. High Availability

Production topology should eliminate obvious single-process failure where practical.

At minimum, design must support:

- restart/replacement of failed application process;
- database backup and recovery;
- worker retry/replay;
- provider outage isolation;
- redundant application instances if justified by the pilot availability target.

Exact redundancy level is set by approved Production SLO/RTO requirements.

## 17. Database High Availability

Database HA mode is selected based on approved pilot reliability requirements.

Regardless of implementation, failover must preserve:

- committed transaction integrity;
- journal consistency;
- outbox/inbox correctness;
- aggregate versions;
- unique idempotency constraints.

A database failover that loses acknowledged financial transactions is unacceptable outside an explicitly approved recovery boundary.

## 18. Backup Requirements

Production requires automated backups.

Backups must cover:

- transactional database;
- critical configuration metadata where not reproducible;
- evidence metadata;
- required object-storage data;
- key configuration references where appropriate.

Backup success alone is insufficient; restore must be rehearsed and verified.

## 19. RPO / RTO

Exact numeric Recovery Point Objective and Recovery Time Objective are not invented in Technical documentation.

Before Production approval, explicit RPO/RTO targets must be approved.

Technical design must support defining and testing them.

Financial-data loss tolerance must be treated separately from general service downtime.

## 20. Disaster Recovery

Pilot disaster recovery must at least define:

- authoritative backup source;
- restore sequence;
- secret/key restoration;
- application deployment restoration;
- provider integration restart;
- outbox/inbox recovery;
- post-restore reconciliation;
- ledger integrity verification;
- business stop controls during recovery.

Recovery must end with business-integrity verification, not just process restart.

## 21. Deployment Strategy

Deployment should support controlled incremental release.

Permitted strategies may include:

- rolling;
- blue/green;
- canary where operationally justified.

For database-backed financial changes, schema compatibility governs deployment strategy.

No deployment strategy may allow two incompatible application versions to interpret the same financial state differently.

## 22. Schema Migration Compatibility

Migrations must be planned for staged deployment.

Prefer:

```
expand
→ deploy compatible code
→ backfill if needed
→ verify
→ contract/remove old structure later
```

Avoid destructive schema changes in the same step as application rollout.

Financial history must never be discarded to simplify migration.

## 23. Rollback

Application rollback is permitted only when the previous version is compatible with current schema/data and policy semantics.

If a migration or business event cannot safely roll back, use forward-fix with stop controls rather than pretending rollback is safe.

Posted journals/events are never rolled back by infrastructure deployment rollback.

## 24. Artifact Immutability

Every deployed artifact must have:

- source commit;
- immutable artifact digest/version;
- build ID;
- dependency/security scan result;
- environment deployment record.

Production must run exactly identified artifacts.

## 25. Configuration Management

Runtime configuration is externalized from code where appropriate.

Configuration classes:

- non-sensitive app settings;
- provider endpoints;
- rate limits;
- security settings;
- feature flags;
- adapter mapping version;
- telemetry settings.

Sensitive configuration remains in secret/key manager.

Configuration changes affecting financial behavior require change control and audit.

## 26. Feature Flags

Feature flags are operational controls, not replacements for business governance.

Flags may safely restrict/disable features.

Flags must not silently:

- enable Direct Lending;
- bypass maker-checker;
- disable reconciliation gates;
- skip ledger posting;
- weaken legal authorization;
- change ownership rules;
- activate unapproved policy.

## 27. Runtime Time Source

All runtimes must use reliable synchronized system time.

Requirements:

- UTC or timezone-aware storage;
- offset-aware API/event timestamps;
- clock monitoring;
- no business logic based on browser clock.

Provider event time and Badban received/processed time remain separate fields.

## 28. Financial Precision NFR

All financial/quantity calculations use exact decimal/numeric arithmetic.

NFR requirements:

- no binary float in financial domain;
- explicit scale/precision;
- deterministic rounding;
- versioned rounding rules;
- reproducible historical calculations.

## 29. Transactional Correctness NFR

Hard correctness requirements:

- no double reservation;
- no duplicate financial posting;
- no duplicate repayment effect;
- no duplicate claim settlement;
- no stale version overwrite;
- no unbalanced journal;
- no activation with loan/guarantee mismatch.

These are zero-tolerance correctness properties, not statistical SLOs.

## 30. Idempotency NFR

All repeatable financial/integration commands must remain safe under:

- client retry;
- worker retry;
- provider duplicate callback;
- process crash/restart;
- broker redelivery;
- network timeout.

Exactly-once business effect is achieved through idempotency, not assumed from transport.

## 31. Availability NFR

Availability targets differ by capability.

Examples:

- participant reads;
- staff operational queries;
- financial commands;
- provider event ingestion;
- reconciliation;
- reporting.

Numeric targets must be approved later.

Financial correctness takes precedence over accepting unsafe commands during dependency failure.

## 32. Performance NFR

Exact latency targets are deferred to approved SLOs.

Technical design must support measuring separately:

- participant/read API;
- operational workspace queries;
- guarantee reservation;
- activation;
- journal posting;
- provider request;
- reconciliation batch;
- projection freshness.

Performance optimization must not weaken transaction isolation or auditability.

## 33. Capacity NFR

Before Production, expected pilot envelope must be documented for at least:

- participants;
- active Asset Positions;
- active guarantees;
- daily commands;
- provider events;
- journal postings;
- reconciliation records;
- evidence storage.

No arbitrary production scale numbers are invented here.

Load testing uses the approved pilot envelope plus safety margin.

## 34. Scalability Strategy

Scale in this order:

1. optimize queries/indexes;
2. scale stateless API/workers;
3. partition background workload;
4. optimize read projections;
5. scale database capability;
6. only then consider service decomposition if a demonstrated bottleneck/ownership need exists.

Premature microservices are explicitly not a Technical goal.

## 35. Consistency NFR

Badban-owned financial state uses strong transactional consistency.

Eventual consistency is acceptable for:

- derived read models;
- dashboards;
- telemetry;
- non-authoritative projections.

Any UI showing an eventually consistent projection must not be used as the sole input for a high-impact domain command without server-side authoritative revalidation.

## 36. Read-Model NFR

Read models must:

- expose freshness;
- be rebuildable;
- not mutate source truth;
- preserve authorization scope;
- tolerate asynchronous lag without causing incorrect financial decisions.

## 37. Security NFR

The accepted Security contract is mandatory.

Production requires:

- encrypted transport;
- encrypted sensitive storage/backups;
- least privilege;
- MFA for privileged humans;
- provider authentication;
- secret manager;
- environment separation;
- audit;
- no Critical unresolved security finding at Release gate.

## 38. Auditability NFR

For every material financial/legal action, the system must reconstruct:

- actor/system;
- command;
- authorization;
- maker/checker if applicable;
- prior/new state;
- policy/algorithm version;
- evidence;
- journal/control effect;
- provider references;
- correlation chain.

## 39. Reproducibility NFR

Historical decisions must be reproducible using captured:

- inputs;
- policy versions;
- algorithm version;
- valuation;
- risk snapshot;
- provider evidence;
- rounding rules.

Current external data must not be substituted during historical replay.

## 40. Reconciliation NFR

Every external authoritative domain must have a reconciliation path.

No production provider integration may rely only on callbacks/events.

Reconciliation freshness and unresolved critical mismatches are part of Business Readiness.

## 41. Recoverability NFR

The system must recover safely from:

- application crash;
- worker crash;
- broker outage;
- provider outage;
- provider timeout/unknown outcome;
- database restart/failover;
- deployment interruption;
- duplicate event delivery.

Recovery must not duplicate financial effects.

## 42. Maintainability NFR

Technical implementation should preserve module boundaries aligned to accepted aggregates/domains.

Requirements:

- no cross-module direct table mutation without defined application/domain contract;
- shared utilities must not become business-logic dumping grounds;
- provider code stays behind adapter boundary;
- policy calculations remain deterministic/testable;
- migration history remains controlled.

## 43. Testability NFR

Every hard invariant must be automatable.

Required test classes:

- unit tests for deterministic calculators;
- aggregate/state-machine tests;
- transaction/concurrency tests;
- ledger balancing tests;
- API contract tests;
- event idempotency/order tests;
- provider adapter contract tests;
- reconciliation tests;
- RBAC/maker-checker tests;
- security tests;
- migration tests;
- restore/recovery tests;
- end-to-end pilot golden path.

## 44. Localization / Presentation NFR

Participant/staff UI may localize human-readable text.

Machine contracts remain stable and language-independent:

- reason codes;
- states;
- account codes;
- event types;
- API field names.

Localization must not change financial meaning.

## 45. Accessibility NFR

User interfaces should support practical accessibility appropriate to participant/staff workflows, including:

- keyboard-operable critical actions;
- readable contrast;
- meaningful labels;
- clear error/block explanations;
- non-color-only status communication.

Exact compliance target may be approved during product/UI implementation.

## 46. Data Retention NFR

Retention periods are deferred to legal/accounting approval.

Architecture must support configurable retention while preserving required immutability and referential integrity for:

- journal;
- audit;
- provider evidence;
- guarantee/claim/recovery;
- policy snapshots;
- reconciliation.

## 47. Privacy NFR

Data minimization is mandatory.

The system must support:

- purpose-limited access;
- field suppression;
- scoped exports;
- separation of identity from financial records where practical;
- controlled evidence access.

Deletion/anonymization behavior must not destroy legally required financial/audit history.

## 48. Observability NFR

All critical workflows must emit enough telemetry to detect:

- failed commands;
- stuck states;
- backlog;
- provider degradation;
- stale reconciliation;
- financial invariant failure;
- security anomaly.

Observability may not leak secrets or unnecessary PII.

## 49. Operational NFR

Production requires:

- runbooks;
- alert ownership;
- provider escalation paths;
- stop controls;
- deployment rollback/forward-fix plan;
- backup monitoring;
- restore rehearsal;
- reconciliation monitoring;
- incident process.

## 50. Technology Selection Boundary

This document defines required capabilities rather than mandating a vendor/product stack.

Technology selection must demonstrate compatibility with all accepted Technical contracts.

A chosen stack must not force weakening:

- ACID guarantees;
- exact decimals;
- append-only ledger/audit;
- transactional outbox/inbox;
- provider adapter isolation;
- reconciliation;
- RBAC/maker-checker;
- security;
- observability.

## 51. Production Activation Boundary

Completing this Technical document does not authorize Production or a real-money pilot.

Production remains blocked by:

- Decision 0016 activation requirements;
- Stage;
- QA/Testing;
- Release Approval;
- provider/legal validation;
- approved numeric Pilot Policy Pack;
- production security and operational gates.

## 52. Technical Definition of Done Contribution

With acceptance of this document, the Technical architecture has explicit contracts for:

- system/trust boundaries;
- aggregates;
- state machines;
- persistence;
- ledger;
- policy/versioning;
- APIs;
- events;
- provider adapters;
- reconciliation;
- identity/RBAC;
- security;
- observability;
- deployment/runtime;
- NFRs.

The next step is a **Technical Stage Completion Review** against the parent delivery process before entering Scrum/Product Backlog.
