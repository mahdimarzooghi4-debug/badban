# Badban Scrum / Product Backlog

- **Stage:** Scrum/Product Backlog Complete for Bounded Pilot — Sprint Planning Authorized
- **Status:** Complete
- **Entry Gate:** Decision 0018
- **Exit Gate:** Decision 0019
- **Scope:** bounded external-lender pilot defined by Decision 0016
- **Sprint Execution / Code Authorization:** NOT YET GRANTED
- **Real-Money / Production Authorization:** NOT GRANTED

## Parent delivery process

**Business ✓ → Technical ✓ → Scrum/Product Backlog ✓ → Sprint Planning → Sprint → Code → Code Review → Stage → QA/Testing → Release Approval → Production → Monitoring → Improvement**

This stage has translated the accepted Business and Technical contracts into an ordered, testable, dependency-aware backlog suitable for Sprint planning.

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

1. Every backlog item traces to Accepted Business/Technical contracts.
2. No backlog item may invent unresolved Business values, legal authority, accounting mappings, provider facts, or production thresholds.
3. Direct Lending remains outside the bounded pilot.
4. Financial correctness and recoverability have priority over convenience or premature scale.
5. Provider-specific behavior remains behind adapters.
6. High-impact workflows require authorization, idempotency, policy/version snapshotting, audit, reconciliation, and tests where applicable.
7. Sprint selection must respect dependency order.
8. No Code begins until the selected Sprint scope satisfies Definition of Ready and the Sprint plan is explicitly accepted.
9. Product Backlog completion does not grant real-money activation.

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
- `docs/decisions/0001-0019`
- `docs/technical/00-15`

The backlog remains subordinate to Accepted decisions and Technical contracts.

## Accepted Backlog Documents

- [01 — Ordered Product Backlog](./01-ordered-product-backlog.md) — **Accepted**
- [02 — Definition of Ready and Definition of Done](./02-definition-of-ready-and-done.md) — **Accepted**
- [03 — Dependency Order and Sprint-Ready Delivery Slices](./03-dependency-order-and-delivery-slices.md) — **Accepted**
- [04 — Product-Backlog Stage Completion Review](./04-product-backlog-stage-completion-review.md) — **PASS / Accepted**

## Stage Exit Result

Product Backlog stage completion review: **PASS**

Sprint Planning is authorized by Decision 0019.

Sprint execution and Code remain blocked until an explicit Sprint Goal, Sprint Backlog, implementation choices, acceptance tests, dependencies, non-goals, and Definition-of-Ready evidence are accepted for the selected slice.

## Next Stage

The next repository work is **Sprint Planning**, normally beginning with Slice 0 — Implementation Foundation and BL-001 through BL-005 unless a dependency-supported alternative is explicitly approved.
