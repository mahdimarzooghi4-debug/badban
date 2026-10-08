# Sprint 14 — Reconciliation Engine Core and Lender Baseline

- **Status:** Accepted / Code Authorized
- **Date:** 2026-10-08
- **Stage:** Sprint
- **Scope:** backend-first / BL-042 Core + lender vertical slice
- **Entry Gate:** Sprint 13 merged; post-merge CI #295 green
- **Depends on:** BL-024, BL-025, BL-030, BL-041; Decision 0039
- **Code Authorization:** GRANTED BY DECISION 0040

## 1. Sprint Goal

Implement the governed Reconciliation Engine Core and a real source-backed lender reconciliation path without inventing policy values, provider contracts, resolution workflow, or command blocks.

## 2. Definition of Ready Evidence

Ready because:

- BL-024 is complete and exposes an authenticated provider-generic lender adapter plus reconciliation snapshot contract;
- BL-025 is complete and provides ExternalLoanMirror;
- BL-030 is complete and provides append-only journal truth;
- BL-041 is complete and provides integration reliability primitives;
- Technical 10 is Accepted;
- Decision 0039 resolves ownership/versioning of freshness, tolerance, and materiality rules;
- no real provider is required for the internal provider-neutral implementation; production connectivity remains unavailable unless configured.

## 3. Authorized Persistence

Implement:

- `reconciliation_runs`;
- `reconciliation_cases`;
- `reconciliation_observations` append-only;
- exact rule-policy lineage;
- source cutoffs/references/evidence;
- deterministic source-snapshot/rule-version fingerprint.

No `reconciliation_blocks` in this Sprint.

## 4. Authorized Runtime

The lender runner:

1. resolves the exact active Pilot Policy Pack;
2. resolves exactly one governed `RECONCILIATION_POLICY` component;
3. resolves the configured lender adapter;
4. fetches the authoritative lender reconciliation snapshot;
5. compares it to provider-scoped ExternalLoanMirror state;
6. checks the linked guarantee principal invariant where linkage exists;
7. persists immutable run/case/observation evidence;
8. writes audit/outbox;
9. never mutates journal history or guarantee financial state.

## 5. Fail-Closed Rules

The Sprint must fail closed for:

- missing/ambiguous policy pack;
- missing/invalid reconciliation policy;
- missing required freshness/materiality configuration;
- unconfigured/unavailable lender adapter;
- stale source;
- duplicate external records;
- insufficient source identity/evidence;
- provider/scope mismatch.

No stale or unavailable source becomes MATCHED.

## 6. API

Authorized:

- `POST /api/v1/reconciliation/runs`;
- `GET /api/v1/reconciliation/runs/{id}`;
- `GET /api/v1/reconciliation/cases`;
- `GET /api/v1/reconciliation/cases/{id}`.

No resolution mutation endpoint is implemented in Sprint 14.

## 7. Tests

Cover at least:

- exact match;
- missing external;
- missing internal;
- duplicate external;
- amount/currency/state mismatch;
- stale snapshot;
- hard guarantee/loan principal mismatch is CRITICAL;
- missing policy fails closed;
- missing adapter/provider outage fails closed;
- duplicate same snapshot/rule is idempotent;
- observations are DB append-only;
- reconciliation never mutates journal or GuaranteeCase financial state;
- authorization is provider-scoped;
- OpenAPI exposes no resolution/block mutation API.

## 8. Explicit Non-Goals

No BL-020/021/022/023/026, no BL-043, no real provider credentials, no fabricated external sources, no UI/Figma/frontend, no automatic Stage, no Release/Production.
