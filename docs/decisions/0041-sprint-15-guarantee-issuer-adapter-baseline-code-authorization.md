# Decision 0041 — Sprint 15 Guarantee Issuer Adapter Baseline; Code Authorization

- **Status:** Accepted
- **Date:** 2026-10-08
- **Scope:** Sprint 15 / Guarantee Issuer Integration Foundation / Code Authorization
- **Depends on:** BL-001, BL-003, BL-017, BL-018; Technical 09 §19
- **Authorizes:** BL-022 only

## Decision

Accept Sprint 15 and authorize Code for **BL-022 — Guarantee Issuer Adapter Baseline**.

The implementation must remain provider-generic and must use the Accepted Provider Adapter Contract without inventing a real Guarantee Issuer API, credential, transport contract, timeout value, retry budget, or provider-specific mapping.

## Authorized Boundary

Sprint 15 may implement:

- a Guarantee Issuer adapter protocol/interface;
- capability manifest;
- normalized outbound command/result boundary;
- normalized issuer state query/result boundary;
- authenticated inbound verification/normalization boundary;
- normalized reconciliation snapshot boundary;
- normalized provider-error translation;
- adapter health;
- provider-scoped adapter registry;
- exact contract/mapping/normalization version identifiers.

Common provider-adapter semantics should reuse the conventions already established by the lender adapter where those semantics are defined by Technical 09.

## Canonical Events

Only these canonical inbound events are authorized:

- `GUARANTEE_ISSUED`
- `GUARANTEE_CANCELLED`
- `GUARANTEE_RELEASED`
- `CLAIM_ACKNOWLEDGED`
- `CLAIM_SETTLEMENT_CONFIRMED`

Provider-specific status values remain behind versioned adapter mapping.

## Legal-Issuance Boundary

**BL-023 — Confirm Legal Guarantee Issuance is NOT authorized.**

Therefore an issuer adapter fact, including `GUARANTEE_ISSUED`, is authoritative input/evidence only. Sprint 15 must not:

- transition GuaranteeCase to ISSUED;
- consume or alter BackingAllocation;
- equate RESERVED with legal issuance;
- activate an external loan;
- create journal/control effects for legal issuance;
- bypass legal authorization or maker-checker rules.

The later BL-023 domain command remains responsible for accepting authoritative issuance evidence into the GuaranteeCase lifecycle.

## Security Boundary

No real secret, token, certificate, API key, or provider credential may be stored in source code, normal database rows, API responses, or logs.

The baseline exposes authentication capability/verification boundaries only. A concrete provider authentication implementation is not implied or fabricated.

## Error and UNKNOWN_OUTCOME Semantics

Technical 09 provider classifications remain authoritative:

- `RETRYABLE`
- `NON_RETRYABLE`
- `UNKNOWN_OUTCOME`

A timeout or ambiguous transport response must never be interpreted as issuance success or failure.

No hard-coded timeout/retry/backoff values are authorized.

## Reconciliation Boundary

The adapter may expose an authoritative normalized issuer snapshot needed by future reconciliation.

Sprint 15 does not implement issuer-side BL-042 reconciliation cases, BL-043 resolution/blocking, or any direct repair path.

## Explicit Non-Goals

No BL-020, BL-021, BL-023, BL-026, claim domain workflow, settlement workflow, real issuer connectivity, provider certification, Stage, QA/Testing, Release Approval, Production, or real-money behavior.

## Approval Effect

Code is authorized only for BL-022 within the Sprint 15 plan.

The Sprint PR must remain Draft/Open through Code Review and must not be merged without explicit user instruction.
