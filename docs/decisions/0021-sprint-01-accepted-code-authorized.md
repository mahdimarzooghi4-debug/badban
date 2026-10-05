# Decision 0021 — Sprint 01 Accepted; Code Authorized for Foundation Scope

- **Status:** Accepted
- **Date:** 2026-10-05
- **Scope:** Sprint Gate / Code Authorization / Bounded External-Lender Pilot
- **Dependencies:** Decision 0019; Decision 0020; Sprint 01 — Implementation Foundation Plan

## Decision

Sprint 01 — Implementation Foundation is Accepted.

Code is authorized **only for the Sprint 01 selected scope BL-001 through BL-005**.

This authorization is narrow and does not permit implementation of later Business capabilities.

## Authorized Code Scope

Sprint 01 may implement:

- repository/application skeleton;
- backend package/module boundaries;
- worker entry point;
- typed configuration foundation;
- environment/secret-reference boundary;
- PostgreSQL connection/session infrastructure;
- SQLAlchemy metadata/base conventions;
- Alembic configuration and initial infrastructure migrations;
- exact-decimal persistence conventions;
- optimistic-version convention;
- foundational idempotency/outbox/inbox persistence;
- NATS JetStream transport abstraction and smoke path;
- OpenTelemetry/correlation/structured logging foundation;
- liveness/readiness foundation;
- CI quality gates;
- container/Compose development and CI foundation;
- minimal frontend skeleton only if needed for common tooling.

## Explicitly Unauthorized

Sprint 01 Code must not implement:

- Program/ParticipationEpisode business workflows;
- Asset Type Registry business behavior;
- Asset Position;
- valuation;
- Policy Pack lifecycle;
- guarantee capacity;
- provider/product business registry;
- legal authorization business workflow;
- guarantee request/reservation/issuance;
- external loan mirror/activation;
- financial posting templates;
- claims/recovery;
- return allocation;
- entitlement;
- exit;
- real provider credentials;
- real payment;
- Direct Lending;
- Production deployment.

## Stack

Sprint 01 must use Accepted Decision 0020:

- Python 3.12;
- FastAPI;
- Pydantic v2;
- SQLAlchemy 2.x async;
- asyncpg;
- Alembic;
- PostgreSQL 16+;
- NATS JetStream;
- Keycloak integration seams;
- S3-compatible evidence storage / MinIO for development-compatible environments;
- HashiCorp Vault target for Stage/Production secrets;
- OpenTelemetry;
- Prometheus/Grafana/Loki/Tempo-compatible observability;
- React + TypeScript + Vite;
- Pytest / pytest-asyncio / Hypothesis;
- Ruff / Pyright;
- GitHub Actions;
- Docker / OCI / Docker Compose.

## Definition-of-Done Gate

Sprint 01 is not complete merely because code exists.

The Sprint must satisfy its Accepted Definition of Done, including:

- CI quality gates active and green;
- migrations valid from empty database;
- persistence conventions encoded/tested;
- transaction rollback safety test;
- outbox/inbox transaction/deduplication tests;
- NATS smoke/recovery behavior;
- correlation/observability foundation;
- no committed production secrets;
- no accidental later Business workflow implementation;
- documentation synchronized with implemented reality.

## Next Gate

After Sprint 01 Code is implemented, work proceeds to:

```
Code
→ Code Review
```

Sprint 02 planning does not authorize itself automatically from Sprint 01 completion.

## Production Boundary

This decision does not authorize:

- Stage;
- QA/Testing;
- Release Approval;
- Production;
- real-money pilot activation.

All later gates remain mandatory.

## Consequence

The repository may now enter **Code** for Sprint 01 foundation scope only.
