# Decision 0020 — Initial Implementation Stack for Bounded Pilot

- **Status:** Proposed
- **Date:** 2026-10-05
- **Scope:** Technical Implementation / Sprint 01 Foundation
- **Dependencies:** Decision 0018; Decision 0019; Accepted Technical 00-15; BL-001

## Decision

Use a Python/PostgreSQL modular application stack for the bounded external-lender pilot, with explicit separation between the transactional core, asynchronous workers, provider adapters, identity, evidence storage, secrets, and observability.

The proposed initial implementation stack is:

### Backend / Domain

- **Python 3.12**
- **FastAPI** for HTTP APIs
- **Pydantic v2** for schema/contract validation
- **SQLAlchemy 2.x async** for relational persistence
- **asyncpg** as PostgreSQL driver
- **Alembic** for database migrations

### Authoritative Database

- **PostgreSQL 16+**

PostgreSQL remains the single authoritative relational transactional store for Badban-owned operational state in the bounded pilot.

### Async / Integration Transport

- **NATS JetStream**

Use NATS JetStream for durable asynchronous delivery, while preserving the accepted transactional outbox/inbox model.

Exactly-once transport is not assumed.

### Identity

- **Keycloak** using OIDC/OAuth2

Badban remains authoritative for current fine-grained role/scope grants and maker-checker rules.

### Object / Evidence Storage

- **S3-compatible object storage**
- **MinIO** for local/test/stage-compatible development environments

Production object-storage provider may be a managed S3-compatible service, provided the accepted evidence/security contract remains satisfied.

### Secrets / Key Management

- **HashiCorp Vault** as the default Stage/Production secret-management target

Local development may use non-production environment-injected secrets that are excluded from Git, while retaining the same logical secret-reference abstraction.

### Observability

- **OpenTelemetry** for traces/metrics/log correlation
- **Prometheus-compatible metrics**
- **Grafana** dashboards
- **Loki-compatible structured log backend**
- **Tempo-compatible trace backend**

The application must remain portable across compatible managed implementations.

### Frontend

- **React**
- **TypeScript**
- **Vite**

Frontend is not an authoritative calculation or financial-state engine.

### Test / Quality Toolchain

- **Pytest**
- **pytest-asyncio**
- **Hypothesis** where property/concurrency-oriented tests materially improve invariant coverage
- **Ruff**
- **Pyright**

### Build / CI

- **GitHub Actions**
- **OCI/Docker images**
- dependency/security scanning and secret scanning as mandatory quality gates

### Runtime Packaging

- **Docker / OCI containers**
- **Docker Compose** for local development and CI integration environments

Stage/Production must run the same OCI artifacts. The exact managed container-hosting vendor remains an operational selection before Stage, because numeric SLO/RPO/RTO and production hosting constraints are not yet approved.

This vendor deferral does not change application/runtime contracts.

## Rationale

This stack satisfies the accepted Technical requirements for:

- ACID financial transactions;
- exact decimal/numeric persistence;
- optimistic concurrency;
- append-only financial history;
- transactional outbox/inbox;
- provider adapter isolation;
- OIDC/MFA-capable identity integration;
- durable asynchronous processing;
- evidence storage;
- centralized secrets;
- observability;
- containerized reproducible delivery;
- automated contract/invariant testing.

It also avoids introducing a microservice requirement into the bounded pilot.

## Explicit Non-Selections

For Sprint 01:

- no event-sourced authoritative model;
- no NoSQL authoritative financial database;
- no binary floating-point financial arithmetic;
- no client-side authoritative financial calculations;
- no serverless-per-function decomposition;
- no direct-lending runtime;
- no Temporal/workflow engine unless a later Accepted decision demonstrates a concrete need;
- no production cloud vendor lock-in before operational targets and Stage requirements are approved.

## Architectural Boundary

The codebase should remain a modular monolith / modular transactional core even though API, worker, reconciliation, and scheduler process roles may execute separately.

Logical module boundaries follow Accepted Technical domain contracts.

## Consequences

1. Sprint 01 can create the repository/application foundation without reopening Business semantics.
2. PostgreSQL transaction boundaries remain the primary correctness mechanism.
3. NATS is asynchronous transport only; outbox/inbox and idempotency remain mandatory.
4. Keycloak authentication does not replace Badban server-side authorization.
5. provider-specific libraries remain behind adapter interfaces.
6. infrastructure vendor choice may remain portable until Stage hosting is selected.
7. any later stack replacement that affects accepted Technical invariants requires a new repository decision.

## Approval Effect

If Accepted, this decision satisfies the implementation-stack selection required by BL-001 for Sprint 01 Code entry, except for the exact managed Stage/Production hosting vendor, which is explicitly deferred to the Stage-environment implementation decision because it is not required to begin application Code safely.
