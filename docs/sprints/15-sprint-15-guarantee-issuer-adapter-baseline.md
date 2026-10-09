# Sprint 15 — Guarantee Issuer Adapter Baseline

- **Status:** Code + Code Review Complete / Merge Pending Explicit Approval
- **Date:** 2026-10-08
- **Stage:** Sprint
- **Scope:** backend-first / BL-022 only
- **Entry Gate:** BL-001, BL-003, BL-017, BL-018 complete on `main`
- **Traceability:** Technical 09 §19
- **Code Authorization:** GRANTED BY DECISION 0041

## 1. Sprint Goal

Implement the provider-generic Guarantee Issuer Adapter baseline required by BL-022 without inventing a real issuer API, credentials, provider mapping, timeout values, retry counts, or legal issuance workflow.

## 2. Authorized Contract

The baseline may define:

- Guarantee Issuer adapter protocol/interface;
- capability manifest using the existing provider-adapter vocabulary;
- normalized outbound command/result boundary;
- normalized issuer-state query/result boundary;
- authenticated inbound-message normalization boundary;
- normalized reconciliation snapshot boundary;
- normalized provider error classification;
- adapter health contract;
- provider-scoped adapter registry;
- immutable provider-contract / mapping / normalization / outbound-mapping version identifiers.

The implementation should reuse the conventions already proven by the Lender Adapter where the Accepted Technical contract is common.

## 3. Canonical Inbound Events

Only the Technical 09 §19 canonical Guarantee Issuer events are authorized:

- `GUARANTEE_ISSUED`
- `GUARANTEE_CANCELLED`
- `GUARANTEE_RELEASED`
- `CLAIM_ACKNOWLEDGED`
- `CLAIM_SETTLEMENT_CONFIRMED`

Provider-specific source statuses remain behind the adapter mapping boundary.

## 4. Authoritative Fields

Normalized issuer facts may carry only accepted authoritative fields needed by Technical 09, including:

- guarantee issuer/provider ID;
- external guarantee ID;
- issued amount;
- beneficiary/lender reference;
- issue date;
- provider-authoritative state;
- claim/settlement reference where applicable;
- evidence reference;
- provider contract/mapping/normalization versions.

Money uses exact decimal strings within the existing NUMERIC(38,18) storage boundary.

## 5. Authentication and Secret Boundary

The adapter exposes the authentication boundary but does not invent a real issuer authentication scheme.

Rules:

- provider credentials stay outside domain models and ordinary database rows;
- no secret value enters logs/API/domain payloads;
- no fake production verifier is authorized;
- unauthenticated or failed-verification inbound payloads cannot become trusted normalized issuer facts;
- no provider is certified or activated by this Sprint.

## 6. Error / Retry Semantics

Reuse the Accepted provider error vocabulary:

- `RETRYABLE`
- `NON_RETRYABLE`
- `UNKNOWN_OUTCOME`

and the stable provider error codes already defined by Technical 09.

A timeout never means issuance success or failure by itself.

No retry count, timeout duration, backoff constant, or provider-specific behavior is invented in this Sprint.

## 7. Reconciliation Snapshot Boundary

The adapter must support a normalized issuer reconciliation snapshot containing:

- provider/issuer ID;
- snapshot timestamp;
- source/evidence reference;
- authoritative guarantee records and current states needed by Technical 09.

This Sprint does not implement BL-042 issuer reconciliation comparison/cases.

## 8. Explicit Non-Goals

Sprint 15 does not implement:

- BL-020 Atomic Backing Reservation;
- BL-021 Reservation Expiry;
- BL-023 Confirm Legal Guarantee Issuance;
- BL-026 Guaranteed External Loan Activation;
- claim domain workflow or claim settlement;
- GuaranteeCase transition to ISSUED/ACTIVE/RELEASED;
- BackingAllocation mutation;
- journal mutation;
- real provider API/client;
- real credentials;
- provider certification;
- UI/Figma/frontend;
- Stage/QA/Release/Production;
- real-money behavior.

An internal reservation must never be treated as legal guarantee issuance.

## 9. Test Contract

Tests must prove at least:

- manifest accepts only canonical issuer events;
- malformed/unknown event fails closed;
- exact-decimal issued amount validation;
- required event-specific authoritative fields;
- timezone-aware timestamps;
- blank evidence/reference rejection where required;
- normalized error classification;
- provider-scoped registry resolution and missing-adapter failure;
- reconciliation snapshot validation;
- adapter boundary does not mutate GuaranteeCase, BackingAllocation, or Journal state.

## 10. Delivery Boundary

The Sprint ends at Code + Code Review for BL-022.

PR remains Draft/Open through Code Review and is not merged without explicit user instruction.
