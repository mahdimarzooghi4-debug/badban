# Sprint 09 — Portfolio Risk Snapshot and Gate

- **Status:** Accepted
- **Date:** 2026-10-07
- **Stage:** Sprint Planning
- **Scope:** bounded external-lender pilot
- **Entry Gate:** Sprint 08 / BL-030 Code + Code Review complete and merged; CI #218 green; Decision 0033 reactivates Stage/QA/Release gates
- **Depends on:** BL-013, BL-015, BL-030; Decision 0010; Technical 02, 04, 06, 07, 08, 11
- **Code Authorization:** GRANTED BY DECISION 0034

## 1. Sprint Goal

Implement only:

- **BL-032 — Portfolio Risk Snapshot and Gate**

The Sprint establishes an immutable, reproducible, policy-versioned portfolio-risk snapshot and a fail-closed gate for future exposure-increasing commands.

## 2. Non-Negotiable Risk Boundary

No production numeric risk value is invented by Sprint 09.

The repository already defines the required risk concepts but deliberately leaves production numbers to governance. Therefore:

- no hard-coded portfolio limit;
- no hard-coded reserve ratio;
- no hard-coded warning/stop threshold;
- no guessed default/recovery/stress assumption;
- no implicit GREEN;
- no synthetic PASS when risk inputs or policy are missing.

Evaluation may use only explicit values present in the exact approved Risk Appetite Policy version and explicit evaluated inputs supplied to the deterministic evaluator.

## 3. Authoritative Policy Binding

Every evaluation must:

1. resolve one exact ACTIVE Pilot Policy Pack for scope/effective time;
2. resolve exactly one referenced `RISK_APPETITE_POLICY` component;
3. verify policy payload integrity;
4. reject missing, duplicate, incompatible, non-approved/non-active-for-pack, or malformed risk policy inputs;
5. store the exact policy pack ID/version and risk policy version ID used.

No use of “latest” is allowed.

## 4. Snapshot Contract

`PortfolioRiskSnapshot` is append-only and records at minimum the accepted Technical 04 fields:

- policy pack;
- risk state GREEN / AMBER / RED;
- total active exposure;
- total reserved exposure;
- committed exposure;
- approved portfolio limit;
- reserve requirement;
- reserve available;
- concentration metrics reference;
- optional stress result reference;
- evaluated timestamp;
- created timestamp.

To satisfy reproducibility, the implementation must additionally preserve the exact evaluated input payload/hash, risk policy version, evaluator algorithm/version, and explicit gate-driver evidence/references.

## 5. Deterministic Evaluator

The PortfolioRiskEvaluator must be deterministic and versioned.

It must evaluate only policy rules that are explicitly represented in the versioned Risk Appetite Policy payload. Missing required rule values fail closed with `POLICY_VALIDATION_FAILED` or a stable risk-evaluation error; they are never defaulted.

The evaluator must distinguish:

- GREEN — all hard gates satisfied and no warning gate is breached;
- AMBER — warning condition(s) exist while all hard gates remain satisfied;
- RED — any hard portfolio/risk gate is breached.

RED blocks new exposure growth. Existing obligations are not rewritten.

## 6. API Surface

Implement only the accepted Technical 07 risk endpoints:

    GET  /api/v1/risk/portfolio
    POST /api/v1/risk/portfolio/evaluate

Rules:

- GET returns the latest immutable snapshot for the authorized scope and does not evaluate;
- POST creates a new immutable snapshot;
- POST is privileged and unavailable to participants;
- RISK may view/evaluate within authorized scope;
- AUDITOR may read but not evaluate;
- responses serialize monetary decimals exactly as strings.

## 7. Authorization and Scope

Use existing deny-by-default RBAC.

- `RISK`: read/evaluate risk within authorized scope;
- `AUDITOR`: read only;
- unrelated roles receive no risk mutation authority;
- role expiry/revocation fails closed;
- scope is explicit and cannot be bypassed by unrelated global privileges.

## 8. Audit and Outbox

A successful evaluation commits atomically:

- PortfolioRiskSnapshot;
- audit event;
- `PortfolioRiskEvaluated` outbox event;
- `PortfolioRiskStateChanged` only when a previous snapshot exists for the same scope and its state differs.

Sprint 09 writes to the existing transactional outbox but does not complete BL-041 transport/replay/dead-letter infrastructure.

## 9. Immutability and Concurrency

- snapshots are append-only at DB level;
- one evaluation request is idempotent by exact semantic payload;
- same key + changed payload fails;
- concurrent first execution cannot create duplicate accepted effects;
- a newer snapshot never rewrites an older snapshot.

## 10. Reservation Boundary

Sprint 09 does **not** implement BL-020.

It only exposes the authoritative risk snapshot/gate required by BL-020.

Future reservation must capture a specific risk snapshot and must fail when no valid snapshot/gate is available. No reservation path may convert missing risk into PASS.

## 11. Acceptance Tests

Tests must cover:

- exact Risk Appetite Policy component binding;
- malformed/missing policy fail-closed behavior;
- deterministic GREEN / AMBER / RED classification from explicit policy rules and inputs;
- no implicit GREEN/defaults;
- immutable persistence;
- exact decimals;
- RISK vs AUDITOR authorization;
- idempotent replay/conflict;
- concurrent first evaluation;
- audit/outbox atomicity;
- state-change event semantics;
- OpenAPI contracts;
- no BL-020 reservation behavior.

## 12. Explicit Non-Goals

No BL-016, BL-020, BL-021, BL-031, BL-033, provider integration, claim/recovery, Production, real-money activity, or invented production risk numbers.

## 13. Definition of Done

BL-032 is Done through Code Review when the deterministic policy-bound evaluator, immutable persistence, risk APIs, authorization, idempotency/concurrency, audit/outbox, migration, and tests are complete and full CI is green.
