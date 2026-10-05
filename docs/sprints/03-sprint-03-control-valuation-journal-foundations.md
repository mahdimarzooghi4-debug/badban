# Sprint 03 — Control, Valuation, and Journal Foundations

- **Status:** Accepted
- **Date:** 2026-10-05
- **Stage:** Sprint Planning
- **Scope:** bounded external-lender pilot
- **Entry Gate:** Decision 0023; Decision 0025
- **Depends on:** Sprint 02 Code + Code Review Complete
- **Code Authorization:** GRANTED BY DECISION 0026

## 1. Sprint Goal

Close the prerequisite gaps that currently block the accepted policy/capacity slice.

Sprint 03 establishes:

- maker-checker / ApprovalRequest baseline;
- immutable valuation observations for existing Asset Positions;
- append-only balanced journal engine foundation.

These capabilities unblock later Policy Pack, deterministic capacity, portfolio-risk, provider/legal, claim, return, and settlement work without implementing those downstream workflows early.

## 2. Selected Backlog Items

Sprint 03 includes:

- **BL-008 — Maker-Checker / ApprovalRequest**
- **BL-012 — Immutable Valuation Observation**
- **BL-030 — Append-Only Journal Engine**

All three are Ready from the accepted dependency graph:

- BL-008 depends on BL-007 + BL-004 — Done;
- BL-012 depends on BL-010 + BL-011 — Done;
- BL-030 depends on BL-004 + BL-007 — Done.

## 3. Why Slice 2 Is Not Taken As-Is

The accepted candidate Slice 2 includes BL-013 through BL-016 and BL-032, but its dependencies are not yet all satisfied:

- BL-013 requires BL-008;
- BL-032 requires BL-030 in addition to policy/capacity work.

Therefore Sprint 03 deliberately performs dependency-unblocking work first.

No dependency is bypassed merely to preserve the original slice grouping.

## 4. Dependency Order

```
Sprint 02
├─→ BL-008 Maker-Checker
├─→ BL-012 Immutable Valuation
└─→ BL-030 Append-Only Journal

BL-008 → enables BL-013 Policy Lifecycle
BL-012 → enables BL-015 Capacity
BL-030 → enables BL-032 Risk Gate and later financial flows
```

These three foundations may be implemented in parallel where transaction/migration ordering remains safe.

## 5. BL-008 — Maker-Checker Baseline

Implement reusable `ApprovalRequest` state with the Accepted Technical 11 contract.

Required fields include:

- action type;
- target type/id;
- target aggregate version where applicable;
- maker identity;
- checker identity when decided;
- required checker role;
- explicit scope;
- canonical payload hash;
- reason;
- evidence references;
- status;
- expiry;
- lifecycle timestamps;
- optimistic version.

Required states:

```
PENDING
→ APPROVED
→ REJECTED
→ CANCELLED
→ EXPIRED
```

### Hard Rules

- maker and checker must differ;
- checker must independently satisfy role + scope;
- approval binds to exact canonical payload hash;
- approval binds to target aggregate version when supplied;
- payload change invalidates execution eligibility;
- target-version change invalidates execution eligibility;
- expired/rejected/cancelled approval cannot authorize execution;
- approval never bypasses policy/legal/risk/reconciliation/business gates;
- no shared/synthetic superuser bypass.

Sprint 03 delivers the approval primitive and lifecycle only.

It does **not** activate policy packs, providers, guarantees, claims, or exceptional exits.

## 6. BL-012 — Immutable Valuation Observation

Implement accepted valuation observations attached to Asset Positions.

Capture at minimum:

- Asset Position;
- valued quantity;
- unit price;
- valuation currency;
- FX rate when applicable;
- gross market value;
- source name/reference;
- source or rule version reference;
- observed time;
- received time;
- freshness metadata;
- evidence reference;
- immutable creation timestamp.

### Hard Rules

- exact Decimal / PostgreSQL NUMERIC only;
- accepted valuation rows are append-only;
- correction creates a new observation;
- no UPDATE/DELETE through normal runtime path;
- gross market value is derived from captured inputs, not mutable Asset Position state;
- valuation does not itself create guarantee capacity;
- valuation does not create ledger postings;
- market value is not written back into Asset Position as a mutable balance.

### Freshness

Sprint 03 may compute freshness from explicit observation/source inputs and an explicit caller-supplied or source-rule validity window.

The Sprint must not invent final numeric Pilot Policy Pack thresholds.

Later policy runtime will bind policy-controlled freshness rules explicitly.

## 7. Valuation Ingestion Authorization

Valuation ingestion must be trusted and explicitly authorized.

Allowed baseline paths may include:

- RISK staff with explicit scope; or
- internal/provider SERVICE identity with an explicit valuation-ingest capability.

A normal OPERATIONS role does not gain valuation-authoring permission merely because it can create Asset Positions.

Actor/source/evidence are captured server-side and auditable.

## 8. BL-030 — Append-Only Journal Engine

Implement the Product Journal engine as an internal application capability.

This Sprint does not expose a generic arbitrary-balance mutation API.

### Journal Entry

Capture at minimum:

- business event type/id;
- legal entity reference;
- currency;
- PREPARED / POSTED state;
- effective/posting timestamps;
- reversal link;
- idempotency key;
- actor reference;
- correlation/causation;
- created timestamp.

### Posting

Capture at minimum:

- journal entry;
- product account code;
- legal entity;
- economic owner type/id;
- participant/program/provider/asset/guarantee/claim/reserve dimensions when applicable;
- exact debit;
- exact credit;
- currency.

### Hard Rules

For every POSTED journal:

```
SUM(debit) = SUM(credit)
```

Also:

- no binary float;
- direct mutable balance table is prohibited;
- balances are projections from postings;
- POSTED entries/postings are append-only;
- correction uses linked reversal/adjustment;
- duplicate posting idempotency cannot post twice;
- a reversal cannot silently alter the original entry;
- external-lender loan principal must not become a Badban corporate receivable merely because the journal engine exists.

## 9. Journal Scope in Sprint 03

Sprint 03 builds and proves the engine only.

It must not yet implement:

- guarantee reservation posting;
- claim settlement posting;
- return allocation posting;
- reserve cash movement;
- participant payouts;
- external lender loan accounting;
- production statutory chart-of-accounts mapping.

Those remain downstream business/template work.

## 10. Proposed API / Service Surface

### ApprovalRequest

Logical endpoints may include:

```
POST /api/v1/approval-requests
GET  /api/v1/approval-requests/{id}
POST /api/v1/approval-requests/{id}/approve
POST /api/v1/approval-requests/{id}/reject
POST /api/v1/approval-requests/{id}/cancel
```

No `force-approve` endpoint is permitted.

### Valuation

Logical endpoints may include:

```
POST /api/v1/asset-positions/{id}/valuation-observations
GET  /api/v1/asset-positions/{id}/valuation-observations
GET  /api/v1/asset-positions/{id}/valuation-observations/latest
```

“latest” here is only a query convenience over immutable observations and must not become implicit Policy resolution.

### Journal

Prefer an internal application service plus authorized query endpoints.

A generic public endpoint accepting arbitrary account/debit/credit mutations is prohibited.

## 11. Persistence Deliverables

Expected Sprint 03 schema additions:

- `approval_requests`;
- `valuation_observations`;
- `journal_entries`;
- `journal_postings`.

Database protections should include:

- maker != checker check where checker exists;
- lifecycle/status checks;
- payload hash storage;
- target-version binding;
- valuation append-only trigger/permission guard;
- exact numeric checks;
- posted journal append-only protection;
- debit/credit non-negative checks;
- reversal linkage constraints/indexes;
- idempotency uniqueness within posting domain.

## 12. Acceptance Tests — Maker-Checker

Must prove:

- maker creates PENDING request;
- same identity cannot approve own request;
- wrong checker role denies;
- wrong scope denies;
- valid independent checker can approve;
- reject is final for that request;
- expired approval cannot execute;
- changed payload hash yields `APPROVAL_PAYLOAD_CHANGED`;
- changed target version yields `APPROVAL_TARGET_VERSION_CONFLICT`;
- approval does not execute any downstream policy/provider/financial action by itself;
- approval/audit actor identity comes from authenticated context.

## 13. Acceptance Tests — Valuation

Must prove:

- exact quantity/price/FX arithmetic;
- gross market value reproducible from captured inputs;
- non-gold Asset Type works;
- valuation linked to wrong/nonexistent Asset Position is rejected;
- unauthorized actor is denied;
- accepted observation cannot be UPDATEd or DELETEd;
- correction is a new observation;
- stale/fresh state is computable from explicit captured rules;
- valuation creates no ledger posting;
- Asset Position market value remains absent as mutable state.

## 14. Acceptance Tests — Journal

Must prove:

- balanced journal POST succeeds;
- unbalanced journal POST fails atomically;
- zero/negative invalid posting shape is rejected according to contract;
- exact Decimal survives persistence;
- same idempotency key does not double-post;
- POSTED journal cannot be edited/deleted;
- reversal posts inverse economic effect and links original;
- original remains immutable after reversal;
- balances/read models derive from postings;
- no generic arbitrary balance mutation exists;
- no external-loan receivable is invented.

## 15. Definition of Done

Sprint 03 is Done only when:

- its Code authorization is explicitly Accepted;
- migrations apply from current `main` and drift check is green;
- maker-checker tests are green;
- valuation immutability/freshness tests are green;
- journal balance/immutability/reversal/idempotency tests are green;
- audit/security scope tests are green;
- format/lint/type/security/dependency/container CI gates are green;
- no Policy Pack/capacity/risk/provider/guarantee/claim/return workflow is prematurely implemented;
- documentation matches implemented reality;
- Code Review completes.

## 16. Explicit Non-Goals

Sprint 03 must not implement:

- Policy Pack lifecycle;
- PolicyResolver / DecisionSnapshot;
- guarantee capacity;
- Portfolio Risk Snapshot;
- Provider/Product registry;
- Legal Entity Authorization registry;
- guarantee request/reservation/issuance;
- lender/guarantee adapters;
- external loan mirror;
- claims/recovery;
- return allocation;
- entitlement/exit;
- Stage;
- QA/Release Approval;
- Production;
- Direct Lending;
- real-money use.

## 17. Stage Deferral

Decision 0023 remains in force.

Sprint 03 may be implemented/reviewed while Stage is unavailable, but its reviewed output only accumulates into the future Stage candidate.

## 18. Approval Effect

This plan is **Accepted**.

Decision 0026 authorizes Code only for BL-008, BL-012, and BL-030. Stage remains deferred under Decision 0023.
