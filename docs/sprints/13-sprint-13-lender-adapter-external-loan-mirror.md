# Sprint 13 — Lender Adapter Baseline and External Loan Mirror

- **Status:** Accepted
- **Date:** 2026-10-07
- **Stage:** Sprint Planning
- **Scope:** backend integration/domain foundation
- **Entry Gate:** Sprint 12 / BL-044 merged; post-merge CI #271 green
- **Depends on:** BL-003; BL-004; BL-017; BL-018; BL-041; BL-044
- **Code Authorization:** GRANTED BY DECISION 0038
- **Scope:** BL-024 + BL-025 only

## 1. Sprint Goal

Implement the lender adapter baseline and lender-authoritative ExternalLoanMirror foundation without activating guarantees or inventing a real provider integration.

## 2. BL-024 — Lender Adapter Baseline

Implement:

- provider-generic lender adapter protocol;
- capability manifest;
- authenticated inbound-message result contract;
- normalized lender inbound event contract;
- normalized reconciliation snapshot contract;
- provider error classification;
- versioned provider-contract/mapping/normalization identifiers;
- adapter registry/resolution by provider where configuration exists;
- explicit fail-closed behavior when no adapter/verifier exists;
- contract tests using test-only adapters/stubs.

Canonical inbound events:

- LOAN_APPROVED
- LOAN_DISBURSED
- REPAYMENT_RECEIVED
- LOAN_DELINQUENT
- LOAN_SETTLED
- LOAN_CORRECTED

No provider-specific raw payload enters domain logic.

## 3. Provider Authentication Boundary

Inbound lender event acceptance requires:

- provider ID;
- adapter resolution;
- authentication/verification success;
- schema validation;
- provider scope validation;
- normalized event;
- BL-041 inbox deduplication.

A test adapter may exist only in tests.

No production/dev bypass endpoint that marks arbitrary caller payloads authenticated is permitted.

## 4. Normalized Lender Event

The normalized contract includes at least:

- provider_id;
- external_event_id;
- event_type;
- schema_version;
- external_loan_id;
- event_time;
- received_at;
- original_principal;
- disbursed_principal when applicable;
- outstanding_principal;
- currency;
- repayment_reference when applicable;
- delinquency_state when applicable;
- evidence references;
- payload hash;
- provider contract version;
- adapter mapping version;
- inbound normalization version;
- optional provider event sequence where provider contract supplies one;
- optional Badban guarantee reference only when explicitly present/resolved.

All monetary values are decimal strings.

All timestamps are timezone-aware.

## 5. BL-025 — External Loan Mirror

Implement relational persistence for:

### external_loan_mirrors

Fields from accepted Technical 04:

- id;
- optional guarantee_case_id if schema permits unlinked authoritative mirror;
- provider_id;
- external_loan_id;
- state;
- original_principal;
- outstanding_principal;
- currency;
- disbursed_at;
- settled_at;
- delinquency_state;
- last_provider_event_at;
- last_synced_at;
- reconciliation_status;
- version;
- created_at;
- updated_at.

Required uniqueness:

- provider_id + external_loan_id.

### external_loan_events

Append-only provider history:

- mirror ID;
- provider event ID;
- event type;
- principal delta when applicable;
- outstanding principal reported;
- provider event timestamp;
- received timestamp;
- evidence reference;
- payload hash;
- processing status;
- provider/mapping/normalization version lineage where required.

Duplicate provider event identity must not duplicate state effects.

## 6. Mirror Processing Rules

Authenticated normalized events update the mirror under row lock / optimistic versioning.

Rules:

- provider state is never inferred from unrelated local state;
- older provider event time must not regress current mirror;
- duplicate event returns prior result;
- same event identity with changed payload fails closed via inbox;
- outstanding principal < 0 rejected;
- ordinary event cannot set outstanding principal above original principal;
- provider correction may change reported values only through LOAN_CORRECTED and remains historically visible;
- state correction is append-only event history plus explicit current mirror update;
- no history rewrite.

## 7. Event-Specific Boundaries

### LOAN_APPROVED

May create/update a PENDING mirror when required authoritative identity/principal fields exist.

Does not activate GuaranteeCase.

### LOAN_DISBURSED

May preserve lender-authoritative disbursement data in mirror/event history.

Does not execute BL-026 guarantee activation.

### REPAYMENT_RECEIVED

May be preserved as authoritative event history in Sprint 13, but **must not apply repayment financial/domain effect**; BL-027 owns repayment effect.

### LOAN_DELINQUENT

May preserve provider state/fact in the mirror, but must not transition GuaranteeCase; BL-034 owns Guarantee delinquency processing.

### LOAN_SETTLED

May preserve provider settlement state, but must not release guarantee/backing; later domain commands own closure/release.

### LOAN_CORRECTED

May correct lender-authoritative mirror fields within explicit correction semantics, with append-only history.

## 8. External Loan Read API

Implement:

`GET /api/v1/external-loans/{id}`

Requirements:

- authenticated/authorized read;
- lender/provider identified;
- normalized authoritative current state;
- event/freshness timestamps;
- reconciliation status;
- no provider secret/credential exposure.

No arbitrary mirror mutation API is added.

## 9. Inbound API

Implement Technical 07 lender ingestion endpoint only if authentication is truly delegated to an adapter/verifier abstraction.

The endpoint accepts raw provider request material for the adapter boundary, not caller-authored normalized facts.

If no adapter is registered for the provider, fail closed.

Test-only adapter wiring stays test-only.

## 10. Reconciliation Snapshot Contract

Define adapter method/result for authoritative lender reconciliation snapshots.

The result preserves:

- provider;
- snapshot timestamp;
- source/evidence reference;
- authoritative loan records.

No ReconciliationCase is created in Sprint 13.

## 11. Audit / Inbox / Outbox

Material accepted provider facts and mirror mutations must retain:

- correlation ID;
- provider event identity;
- evidence references;
- adapter contract/mapping/normalization versions;
- audit lineage.

Use existing BL-041/BL-044 primitives.

Do not write monetary journals for lender mirror updates.

## 12. Tests

Cover at least:

- adapter capability manifest;
- authentication success/failure boundary;
- unknown/unregistered adapter fail-closed;
- normalization happy path for all six canonical events;
- malformed/missing authoritative field;
- unknown provider status / contract drift;
- decimal-string validation;
- timezone validation;
- duplicate inbound event;
- same event identity changed payload;
- stale/out-of-order provider event cannot regress mirror;
- provider event sequence gap when sequence is supplied;
- correction event history;
- provider+external loan uniqueness;
- query returns lender of record and freshness;
- disbursement does not activate guarantee;
- repayment does not reduce guarantee/backing;
- delinquency does not transition GuaranteeCase;
- no journal entry from mirror-only updates;
- no generic mirror mutation API;
- reconciliation snapshot mapping contract.

## 13. Definition of Done

BL-024 and BL-025 are Done through Code Review when adapter contracts, authenticated normalization boundary, ExternalLoanMirror persistence/history, read API, reconciliation snapshot contract, regression tests, and full CI are green.

## 14. Explicit Non-Goals

No BL-020/021/022/023/026/027/028/029/033/034/042; no real provider; no real credentials; no provider certification; no guarantee activation; no repayment effect; no backing release; no Stage/QA/Release/Production claim.
