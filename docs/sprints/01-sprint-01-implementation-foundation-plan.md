# Sprint 01 — Implementation Foundation Plan

- **Status:** Accepted
- **Date:** 2026-10-05
- **Stage:** Sprint Planning
- **Scope:** bounded external-lender pilot
- **Entry Gate:** Decision 0019
- **Stack Decision:** Decision 0020 — Accepted
- **Code Authorization:** GRANTED FOR SPRINT 01 ONLY BY DECISION 0021

## 1. Sprint Goal

Establish the implementation foundation required to begin Badban coding without making ad hoc architecture, persistence, security, CI, or observability decisions during implementation.

Sprint 01 is intentionally a foundation Sprint.

It does not deliver a real financial transaction.

## 2. Selected Backlog Items

Sprint 01 selects:

- **BL-001 — Implementation Stack Decision Pack**
- **BL-002 — Repository and CI Quality-Gate Blueprint**
- **BL-003 — Environment, Configuration, and Secret Boundary**
- **BL-004 — Transactional Persistence and Migration Foundation**
- **BL-005 — Observability and Correlation Foundation**

No later business capability is selected into Sprint 01.

## 3. Proposed Implementation Stack

Sprint 01 uses Accepted Decision 0020 as its implementation stack.

Core choices:

- Python 3.12;
- FastAPI;
- Pydantic v2;
- SQLAlchemy 2.x async;
- asyncpg;
- Alembic;
- PostgreSQL 16+;
- NATS JetStream;
- Keycloak;
- S3-compatible evidence storage / MinIO for development-compatible environments;
- HashiCorp Vault as Stage/Production secret-management target;
- OpenTelemetry;
- Prometheus-compatible metrics;
- Grafana;
- Loki-compatible logs;
- Tempo-compatible traces;
- React + TypeScript + Vite;
- Pytest / pytest-asyncio / Hypothesis;
- Ruff / Pyright;
- GitHub Actions;
- Docker / OCI containers;
- Docker Compose for local/CI integration environments.

The exact managed Stage/Production hosting vendor remains deferred until operational targets and Stage constraints are approved.

## 4. In-Sprint Dependency Order

```
BL-001 Stack Decision
→ BL-003 Environment / Secret Boundary
→ BL-004 Persistence / Migration Foundation
→ BL-002 CI Quality Gates
→ BL-005 Observability / Correlation
```

BL-002 and BL-005 may progress in parallel once the relevant stack conventions are fixed.

## 5. Planned Code Deliverables

If this Sprint plan and Decision 0020 are Accepted, the subsequent Code stage for Sprint 01 may create only the foundation required by BL-001 through BL-005.

Expected implementation scope:

### Repository/Application Skeleton

- backend application package/module layout;
- worker process entry point;
- configuration package;
- domain/application/infrastructure module boundaries;
- test package structure;
- frontend skeleton only if required to establish shared tooling.

### Persistence Foundation

- PostgreSQL connection/session infrastructure;
- SQLAlchemy metadata/base conventions;
- Alembic configuration;
- initial infrastructure migration(s) only;
- exact-decimal conventions;
- optimistic-version convention;
- idempotency/outbox/inbox foundational schema where needed for the platform skeleton.

### Environment / Secret Boundary

- typed non-secret settings;
- secret-reference interface;
- local non-production configuration example without real secrets;
- environment separation conventions;
- no production credentials.

### Async Foundation

- NATS JetStream client abstraction;
- publisher/consumer infrastructure interfaces;
- no business event consumers beyond safe foundation smoke tests;
- transactional outbox remains the authoritative publication trigger.

### Identity Foundation

Keycloak-specific business authorization is **not** selected as a Sprint 01 capability.

Sprint 01 may include only identity-client/configuration seams needed so later BL-006 can integrate without restructuring the platform.

### Observability Foundation

- OpenTelemetry initialization;
- correlation ID middleware/context;
- trace propagation primitives;
- structured logging conventions;
- basic liveness/readiness endpoints;
- no claim of business-readiness completeness yet.

### CI Foundation

- dependency installation/cache;
- formatting/lint;
- type checking;
- unit test execution;
- migration validation;
- dependency/security scanning;
- secret scanning;
- container build validation.

## 6. Explicit Non-Goals

Sprint 01 must not implement:

- participant onboarding;
- Program/ParticipationEpisode business workflows;
- Asset Type Registry;
- Asset Position;
- valuation;
- Policy Pack business lifecycle;
- guarantee capacity;
- provider/product registry;
- guarantee reservation;
- guarantee issuance;
- external loan;
- ledger posting business templates;
- claims/recovery;
- return allocation;
- participant exit;
- real provider credentials;
- real-money payment;
- Direct Lending;
- Production deployment.

A foundation abstraction may be introduced only when required by BL-001 through BL-005 and must not pre-implement later Business behavior.

## 7. Definition-of-Ready Evidence

### Business Scope

PASS.

Sprint 01 contains technical enablers only and does not invent unresolved financial/legal product behavior.

### Technical Traceability

PASS.

Selected work traces to:

- Technical 04 — persistence/concurrency;
- Technical 08 — outbox/inbox;
- Technical 11 — future identity boundary;
- Technical 12 — secrets/security;
- Technical 13 — observability;
- Technical 14 — runtime/deployment/NFR;
- Decision 0018;
- Decision 0019.

### Dependencies

PASS subject to acceptance of Decision 0020.

The repository currently contains documentation only, so there is no legacy implementation constraint to preserve.

### Security

PASS for planning.

The Sprint explicitly excludes real provider/production secrets and requires secret scanning and environment separation.

### Testing

PASS for planning.

The Sprint defines foundation tests and CI gates below.

## 8. Acceptance Tests / Verification

Sprint 01 Code is expected to satisfy automated verification including:

### Application Boot

- API process starts in local/test configuration;
- worker process starts in local/test configuration;
- missing required configuration fails clearly;
- no production secret is required.

### Database

- test database connectivity works;
- migrations apply from empty database;
- migration history can be validated;
- exact decimal round-trip test passes;
- transaction rollback test proves failed transaction leaves no partial row state.

### Concurrency Foundation

- aggregate/version helper convention is testable;
- stale expected-version operation returns/confirms conflict semantics at infrastructure test level.

No business aggregate state transition is required yet.

### Outbox / Inbox Foundation

- outbox record can be committed in same DB transaction as a test aggregate/infrastructure record;
- rollback removes both;
- inbox unique/deduplication key prevents duplicate processing record;
- no exactly-once transport assumption is encoded.

### NATS

- local/CI integration test can connect to JetStream;
- publish/consume smoke path works;
- transport failure does not erase pending outbox state.

### Configuration / Secrets

- configuration validation rejects missing required non-secret settings;
- secret values are not emitted by structured logs;
- repository secret scan passes;
- production-key placeholders are not committed as credentials.

### Observability

- correlation ID is created/propagated;
- trace context is propagated across one API-to-worker smoke path where practical;
- liveness endpoint works independently of providers;
- readiness reports required local infrastructure state;
- logs are structured and exclude test secrets.

### CI

Pipeline fails on:

- lint error;
- type error;
- unit/integration test failure;
- migration validation failure;
- detected committed secret;
- disallowed high-severity dependency finding according to the configured initial gate.

## 9. Sprint Definition of Done

Sprint 01 is Done only when:

- Decision 0020 is Accepted;
- repository/application skeleton exists;
- CI quality gates are active;
- local/CI environment can start the required foundation dependencies;
- migrations work from empty state;
- persistence conventions are encoded/tested;
- outbox/inbox foundation is testable;
- NATS transport foundation is testable;
- observability/correlation foundation is present;
- no real Business workflow has been accidentally introduced;
- all Sprint 01 automated checks are green;
- repository docs are updated to match implementation reality.

## 10. Risks and Controls

### Risk — Foundation Overengineering

Control:

- modular monolith remains the application model;
- no microservice decomposition;
- no workflow engine unless later justified;
- no premature provider/business implementation.

### Risk — Async Complexity Before Needed

Control:

NATS is used only as transport; correctness remains PostgreSQL + outbox/inbox.

### Risk — Vendor Lock-In

Control:

provider adapters, S3 compatibility, OpenTelemetry, and OCI artifacts preserve portability.

Stage/Production hosting vendor remains a later operational decision.

### Risk — Security False Confidence

Control:

Sprint 01 establishes boundaries and tests but does not claim production security certification.

## 11. Planned Sprint Output

If accepted and implemented, Sprint 01 should leave the repository ready for Sprint 02 planning around:

```
Identity / RBAC
+ Program / Participation Episode
+ Asset Type
+ Asset Position
+ Audit baseline
```

corresponding primarily to Slice 1.

## 12. Approval Effect

Acceptance of this Sprint plan together with Decision 0020 authorizes Code **only for Sprint 01 selected scope BL-001 through BL-005**.

It does not authorize later backlog items, Stage, Production, or real-money use.
