# Sprint 08 — Append-Only Journal Engine Completion

- **Status:** Accepted
- **Date:** 2026-10-07
- **Stage:** Sprint Planning
- **Scope:** bounded external-lender pilot
- **Entry Gate:** Decision 0023; Sprint 07 Code + Code Review Complete
- **Depends on:** BL-004, BL-007 complete; Sprint 03 journal foundation exists
- **Code Authorization:** GRANTED BY DECISION 0032

## 1. Sprint Goal

Complete only:

- **BL-030 — Append-Only Journal Engine**

Sprint 08 hardens and completes the existing Sprint 03 journal foundation. It does not introduce a parallel ledger.

## 2. BL-020 Readiness Blocker

BL-020 — Atomic Backing Reservation is not Code-authorized in Sprint 08.

Technical 07 §16 requires reservation to pass an authoritative portfolio risk PASS gate. BL-032 — Portfolio Risk Snapshot and Gate — is not implemented.

Therefore Sprint 08 must not allow implicit GREEN, synthetic PASS, hard-coded safe defaults, or reservation without a PortfolioRiskSnapshot.

Prerequisite path:

    BL-030 → BL-032 → BL-020

BL-016 remains separately deferred until authoritative reservation/exposure/hold and portfolio-control sources exist.

## 3. Existing Foundation to Reuse

Sprint 03 already introduced:

- JournalEntry;
- JournalPosting;
- exact numeric persistence;
- balanced-entry validation;
- internal post_journal service;
- internal reverse_journal service;
- derived account totals;
- DB protection for posted journal history;
- append-only posting protection;
- baseline idempotency tests.

Sprint 08 must harden and complete these assets rather than replace them.

## 4. BL-030 Completion Boundary

BL-030 must prove:

- every POSTED entry balances exactly;
- balances are derived from postings, never mutable balance columns;
- POSTED journal entries cannot be silently edited or deleted;
- journal postings cannot be silently edited or deleted;
- corrections use linked reversals/adjustments;
- every posting belongs to one explicit legal-entity context;
- economic-owner dimensions remain explicit;
- exact decimal values are preserved without binary-float or silent storage rounding;
- retry/concurrency does not duplicate financial/control effect;
- audit and transactional outbox accompany material journal state changes.

## 5. Internal Posting Boundary

Sprint 08 does not create a generic public HTTP endpoint to post arbitrary journals.

Business workflows may invoke the internal journal engine only through domain-specific authorized commands. Finance/admin users must not be able to bypass domain policy, settlement evidence, ownership, or business-state invariants by constructing raw debit/credit entries over a generic API.

## 6. Journal Lineage

The platform must be capable of preserving accepted Technical 05 lineage where materially applicable:

- business event type and ID;
- legal entity;
- currency;
- actor/system;
- correlation and causation;
- effective timestamp;
- policy/version reference;
- posting-template code/version reference when supplied by an authorized workflow;
- account-mapping version/reference when supplied;
- evidence/settlement reference when required;
- reversal relationship;
- economic-owner and related domain dimensions.

No production value may be guessed.

## 7. BL-031 Boundary

BL-031 — Product Account Taxonomy and Posting Templates — remains outside Sprint 08.

Sprint 08 must not invent statutory account mappings, production posting templates, template-selection policy, or accounting classifications. Concrete template/mapping lifecycle remains BL-031.

## 8. Posting Rules

The internal journal engine must fail closed for invalid posting structure, unbalanced totals, negative values, ambiguous debit/credit sides, missing legal-entity/currency context, unsupported decimal precision, or missing lineage required by the invoked internal contract.

No implicit rounding rule is invented. No binary float is authoritative monetary input.

## 9. Idempotency and Concurrency

- same idempotency key + same semantic payload returns the same journal result;
- same key + changed payload fails;
- concurrent first-time requests cannot duplicate journal effects;
- one original journal can have at most one accepted reversal;
- reversal retries cannot create a second reversal.

## 10. Reversal Contract

A reversal is a new POSTED journal linked to the original.

- original must exist and be POSTED;
- original rows remain unchanged;
- debit/credit sides are inverted exactly;
- reason is mandatory;
- actor/correlation/approval lineage is retained;
- one original has at most one accepted reversal;
- corrected replacement posting, if any, is a separate future journal operation.

## 11. Accepted API Surface

Sprint 08 may implement only the accepted Technical 07 §28 journal APIs:

    GET  /api/v1/finance/journals
    GET  /api/v1/finance/journals/{id}
    POST /api/v1/finance/journals/{id}/reverse

No arbitrary journal-create API is authorized. Read monetary values are decimal strings.

## 12. Authorization

Use existing deny-by-default RBAC:

- FINANCE_RECONCILIATION may inspect authorized journal scope and initiate reversal;
- AUDITOR may read authorized journal evidence only;
- AUDITOR cannot reverse;
- other roles do not gain journal mutation authority merely from unrelated permissions;
- legal-entity/resource scope remains explicit.

## 13. Maker-Checker

Journal reversal is mandatory maker-checker under Technical 11.

Approval binds to the exact original JournalEntry, reversal action, reason, expected conditions and payload hash. Maker/checker must differ. FINANCE_RECONCILIATION initiates; the checker must be an explicitly authorized governance/approval actor under the accepted matrix. Stale or changed approvals fail closed.

## 14. Audit and Outbox

Successful material journal actions must commit traceability in the same transaction:

- posting → audit + JournalPosted outbox event;
- reversal → audit + JournalReversed outbox event.

Sprint 08 writes accepted events to the existing transactional outbox but does not complete BL-041 publisher/dead-letter/replay infrastructure.

## 15. Acceptance Tests

Tests must cover exact balance/precision, append-only DB enforcement, safe replay and concurrent first-write idempotency, linked reversal, maker-checker, scoped finance/auditor authorization, audit/outbox atomicity, rollback with no partial effects, OpenAPI read/reversal contracts, and absence of a generic create-journal endpoint.

## 16. Definition of Done

Sprint 08 is Done through Code Review only when BL-030 acceptance criteria are satisfied, the existing foundation is hardened rather than duplicated, read/reversal APIs are covered, append-only protections remain intact, audit/outbox and maker-checker are proven, full CI is green, and no BL-031/BL-032/BL-020 behavior is introduced.

Stage remains Deferred under Decision 0023.

## 17. Explicit Non-Goals

Sprint 08 does not implement BL-016, BL-020, BL-021, BL-031, BL-032, BL-033, BL-041 completion, arbitrary journal creation API, reservation/risk logic, provider integrations, real cash movement, statutory mappings, claims/recovery, return allocation, Direct Lending, production accounting values, Stage, QA gate completion, Release Approval, Production, or real-money use.

## 18. Approval Effect

Decision 0032 grants Code authorization only for BL-030 within this boundary.
