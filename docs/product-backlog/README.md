# Badban Scrum / Product Backlog

- **Stage:** Scrum/Product Backlog
- **Status:** Active — Backlog Definition in Progress
- **Entry Gate:** Decision 0018
- **Scope:** bounded external-lender pilot defined by Decision 0016
- **Sprint / Code Authorization:** NOT YET GRANTED
- **Real-Money / Production Authorization:** NOT GRANTED

## Parent delivery process

**Business ✓ → Technical ✓ → Scrum/Product Backlog → Sprint → Code → Code Review → Stage → QA/Testing → Release Approval → Production → Monitoring → Improvement**

This stage translates the accepted Business and Technical contracts into an ordered, testable, implementation-ready backlog.

## Product Goal

Deliver the bounded external-lender Badban pilot as a controlled asset-backed guarantee orchestration system that can:

- maintain participant/program Asset Positions with explicit ownership/funding;
- ingest authoritative valuation;
- derive policy-driven guarantee capacity;
- reserve and encumber backing without double use;
- issue and activate a legal guarantee only through authorized provider roles;
- maintain an authoritative external-loan mirror while the external lender remains lender of record;
- preserve the one-to-one invariant between issued guarantee and external loan principal;
- process repayment, delinquency, claims, recovery, return allocation, entitlement, and exit;
- maintain append-only financial/control records;
- reconcile all external authoritative states;
- enforce RBAC, maker-checker, security, auditability, and operational readiness.

## Backlog Rules

1. Every backlog item must trace to one or more Accepted Business/Technical contracts.
2. No backlog item may invent unresolved Business values, legal authority, accounting mappings, provider facts, or production thresholds.
3. Direct Lending remains outside the bounded pilot.
4. Financial correctness and recoverability have priority over convenience or premature scale.
5. Provider-specific behavior remains behind adapters.
6. High-impact workflows must include authorization, idempotency, policy/version snapshotting, audit, reconciliation, and tests where applicable.
7. Sprint selection must respect dependency order.
8. No Code begins until the selected Sprint slice satisfies the Definition of Ready.
9. Product Backlog acceptance does not grant real-money activation.

## Backlog Statuses

- **Proposed** — defined but not yet accepted into ordered backlog.
- **Ready** — meets Definition of Ready and may be selected for Sprint.
- **In Sprint** — selected by an approved Sprint plan.
- **Done** — satisfies Definition of Done after implementation/review/test gates.
- **Blocked** — dependency or unresolved external requirement prevents safe execution.
- **Deferred** — intentionally outside current pilot or later release.

## Priority Classes

- **P0 — Foundation / correctness prerequisite**
- **P1 — Core pilot golden path**
- **P2 — Required pilot control / servicing**
- **P3 — Operational completeness / hardening**
- **Future — outside bounded pilot**

## Source of Truth

Binding sources:

- `docs/business/00-business-foundation.md`
- `docs/business/02-business-stage-completion-review.md`
- `docs/decisions/0001-0018`
- `docs/technical/00-15`

The backlog is subordinate to Accepted decisions and Technical contracts.

## Current Backlog Documents

- [01 — Ordered Product Backlog](./01-ordered-product-backlog.md) — **Proposed**
- [02 — Definition of Ready and Definition of Done](./02-definition-of-ready-and-done.md) — **Proposed**
- [03 — Dependency Order and Sprint-Ready Delivery Slices](./03-dependency-order-and-delivery-slices.md) — **Proposed**

## Stage Exit

This stage may complete only when:

- backlog scope is accepted;
- P0/P1 items are ordered;
- technical enablers and dependencies are explicit;
- each Sprint candidate has acceptance criteria;
- Definition of Ready / Done is accepted;
- the first Sprint can be selected without inventing Business or Technical rules.

Stage completion may authorize **Sprint planning**, not Production.
