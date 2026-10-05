# Badban Definition of Ready and Definition of Done

- **Status:** Proposed
- **Date:** 2026-10-05
- **Stage:** Scrum/Product Backlog
- **Scope:** bounded external-lender pilot
- **Depends on:** Decision 0018; Accepted Technical 00-15

## 1. Purpose

This document defines the minimum quality bar for moving a Product Backlog Item into Sprint and later calling implemented work Done.

The goal is to prevent Business or Technical ambiguity from being discovered only after coding begins.

## 2. Definition of Ready — General

A backlog item is **Ready** only when all applicable conditions below are satisfied.

### Business / Product

- the item is inside the bounded pilot;
- no unresolved Business decision is being silently invented;
- participant/provider/legal/accounting ownership semantics are known;
- Direct Lending is not implied;
- user/system outcome is explicit.

### Technical Traceability

- the item references the relevant Accepted Technical contracts;
- affected aggregate/state machine is known;
- required policy/version behavior is known;
- persistence/read-model impact is known;
- API/event impact is known where applicable;
- provider/reconciliation impact is known where applicable.

### Acceptance Criteria

- success path is explicit;
- rejection/blocking paths are explicit;
- stable error/reason codes are identified where applicable;
- idempotency/retry semantics are explicit for state-changing work;
- authorization scope is explicit;
- maker-checker requirement is explicit where applicable.

### Data / Migration

- required entities/fields/constraints are known;
- exact decimal/unit/currency behavior is explicit;
- migration/backfill approach is understood;
- append-only/immutable records are identified;
- destructive migration is not hidden inside the item.

### Security

- identity class is known;
- sensitive data classification is known;
- required secret/provider credential boundary is known;
- prohibited log/telemetry fields are known;
- provider callback verification requirements are explicit where applicable.

### Observability / Operations

- required logs/metrics/traces are identified;
- business-control indicator impact is known;
- alert/runbook impact is identified for high-risk flows;
- recovery/replay behavior is explicit where applicable.

### Testing

- unit/domain tests required are known;
- API/contract tests required are known;
- concurrency/idempotency tests are identified where applicable;
- provider/reconciliation test doubles or sandbox assumptions are explicit;
- negative-path tests are listed.

### Dependencies

- predecessor backlog items are Done or explicitly included in the same approved Sprint sequence;
- unresolved external provider/legal dependencies are marked Blocked rather than assumed;
- required implementation-stack choice is already accepted for the selected Sprint.

## 3. Definition of Ready — Financial / High-Impact Items

In addition to the general DoR, financial/high-impact items require:

- target state transition is explicit;
- current and resulting aggregate version semantics are known;
- policy pack / decision snapshot requirements are explicit;
- exact ledger/control posting behavior is referenced;
- rollback vs compensating/reversal behavior is explicit;
- reconciliation prerequisite/block is identified;
- maker-checker requirement is identified;
- failure must be proven to leave no partial financial effect.

Examples include:

- guarantee reservation;
- activation;
- exposure reduction;
- claim approval/settlement;
- recovery allocation;
- return allocation posting;
- journal reversal;
- collateral release/enforcement;
- exit finalization.

## 4. Definition of Ready — Provider Integration Items

Provider integration work additionally requires:

- provider capability/contract shape is known or a stubbed canonical contract is the explicit Sprint objective;
- auth mechanism and secret reference approach are known;
- idempotency support is known;
- timeout / retry / UNKNOWN_OUTCOME behavior is explicit;
- inbound normalization mapping is defined;
- provider-specific errors map to canonical errors;
- reconciliation path is included;
- no provider-specific payload leaks into domain code.

If a real named provider is not yet legally/operationally available, the item may be Ready only for a provider-neutral adapter interface/stub, not for claiming production certification.

## 5. Definition of Ready — UI / Read Model Items

UI/read-model work additionally requires:

- authoritative source vs projection is identified;
- freshness semantics are visible where material;
- actor authorization scope is explicit;
- permitted actions derive from server-side business/authorization state;
- the UI does not calculate authoritative financial values that belong to the server;
- loading/error/blocked/stale states are defined.

## 6. Definition of Done — Code and Review

An implemented item is not Done until:

- implementation matches Accepted Business/Technical contracts;
- code review is complete;
- lint/type/static checks pass;
- automated tests pass;
- no known critical regression remains;
- code contains no embedded production secrets;
- module/provider boundaries are preserved;
- no generic bypass/force-state path was introduced.

## 7. Definition of Done — Domain Correctness

Applicable domain items must prove:

- valid transition succeeds;
- invalid transition fails deterministically;
- stale aggregate version fails;
- authorization failure produces no state change;
- policy failure produces no state change;
- idempotent retry produces one semantic effect;
- duplicate event/provider callback produces one business effect;
- state history/audit is preserved.

## 8. Definition of Done — Financial Correctness

Applicable financial items must prove:

- exact decimal arithmetic;
- journal entries balance;
- no direct balance mutation;
- failed transaction leaves no partial posting/reservation/exposure;
- reversal/correction is append-only;
- participant/program/provider/legal-entity dimensions are preserved;
- one-to-one loan/guarantee invariant is maintained;
- duplicate retry cannot duplicate money/exposure effect.

## 9. Definition of Done — Persistence

- migration is tested from supported prior schema;
- constraints/indexes are present where required;
- immutable/history rows cannot be casually updated/deleted through normal runtime;
- database transaction boundary matches the accepted contract;
- query/read-model performance is reasonable for the approved test envelope;
- rollback/forward-fix behavior is documented where migration is not safely reversible.

## 10. Definition of Done — API / Event Contract

Applicable items must include:

- request/response schema;
- stable machine error codes;
- authorization requirement;
- idempotency/version semantics;
- OpenAPI/schema update;
- event schema/version update where applicable;
- backward compatibility or explicit breaking-version handling.

## 11. Definition of Done — Provider Integration

Applicable provider work must prove:

- authentication success/failure;
- normalized mapping;
- duplicate inbound event handling;
- retryable/non-retryable/unknown-outcome behavior;
- timeout handling;
- contract/schema drift handling;
- secret redaction;
- reconciliation snapshot path;
- sandbox/stub contract tests.

Production provider certification is a later Stage/Release gate.

## 12. Definition of Done — Reconciliation

Applicable reconciliation work must prove:

- exact stable-key matching;
- stale source is not MATCHED;
- materiality classification;
- CRITICAL block activation;
- controlled resolution path;
- maker-checker where required;
- repair uses normal domain/reversal command;
- original mismatch evidence remains immutable.

## 13. Definition of Done — Security

Applicable items must prove:

- deny-by-default authorization;
- cross-scope access is blocked;
- privileged action audit exists;
- sensitive data is not leaked to logs;
- secret/key usage follows environment boundary;
- replay/signature failure is rejected for provider callbacks;
- self-approval is impossible where maker-checker applies.

## 14. Definition of Done — Observability

Critical workflow items must emit enough telemetry to identify:

- command/event name;
- correlation/trace;
- resource/provider reference;
- outcome/reason code;
- latency;
- retry/backlog/freshness condition where applicable.

Telemetry must not become financial source of truth.

## 15. Definition of Done — Documentation

Done work updates, when applicable:

- API contract;
- event contract;
- schema/migration notes;
- operational runbook;
- provider mapping docs;
- architecture decision if a material implementation choice was made.

Repository documentation must describe the implemented reality.

## 16. Definition of Done — Recovery / Reliability

For high-impact work:

- process crash/retry path is tested;
- duplicate/replay path is tested;
- provider timeout/unknown outcome path is tested if applicable;
- recovery does not duplicate financial effect;
- any required reconciliation verification is tested.

## 17. Definition of Done — UI

UI/read-model items must:

- use server-authoritative values;
- expose stale/blocked states where material;
- prevent unauthorized action affordances, while still relying on server-side enforcement;
- avoid implying real payment/settlement before authoritative confirmation;
- display machine state without changing its meaning through localization.

## 18. Sprint Entry Rule

A Sprint may select only items that are **Ready**, except for explicitly identified discovery/enabler items whose purpose is to resolve a documented implementation choice.

A Sprint must not combine "discover unknown Business rule" and "implement that rule" as if the outcome were already approved.

## 19. Sprint Exit Rule

Sprint completion does not automatically mean Production-ready.

Completed Sprint work proceeds through:

```
Code Review
→ Stage
→ QA/Testing
→ Release Approval
→ Production
```

under the parent delivery process.

## 20. Hard DoR / DoD Invariants

1. No unresolved Business ambiguity is converted into code by assumption.
2. Every high-impact item has explicit authorization, policy, idempotency, audit, and test semantics.
3. Every financial item has explicit failure atomicity.
4. Every provider item has reconciliation.
5. Every Done claim is supported by automated evidence, not only manual observation.
6. Product Backlog acceptance does not waive Stage/QA/Release gates.
