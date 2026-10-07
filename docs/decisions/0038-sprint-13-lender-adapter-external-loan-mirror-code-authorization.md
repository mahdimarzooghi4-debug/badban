# Decision 0038 — Sprint 13 Lender Adapter Baseline and External Loan Mirror; Code Authorization

- **Status:** Accepted
- **Date:** 2026-10-07
- **Scope:** Sprint 13 / External Lender Integration Foundation / Code Authorization
- **Depends on:** BL-003; BL-004; BL-017; BL-018; BL-041; BL-044; Technical 02; Technical 03; Technical 04; Technical 07; Technical 08; Technical 09
- **Authorizes:** BL-024 and BL-025 only

## Decision

Accept Sprint 13 and authorize Code for the following tightly coupled backend capabilities:

- **BL-024 — Lender Adapter Baseline**
- **BL-025 — External Loan Mirror**

BL-024 is implemented first inside the Sprint. BL-025 may consume only authenticated, normalized lender facts produced through the BL-024 boundary.

## Rationale

This package unlocks the lender-side authoritative mirror and materially reduces the dependency chain toward BL-042 Reconciliation Engine Core.

The accepted Technical contracts already define:

- provider adapter boundaries;
- authentication and secret isolation;
- normalized lender event vocabulary;
- required authoritative lender fields;
- duplicate-event/inbox behavior;
- error and UNKNOWN_OUTCOME semantics;
- reconciliation snapshot capability;
- ExternalLoanMirror ownership and invariants;
- ExternalLoanMirror persistence shape;
- provider-scoped lender ingestion and external-loan query contracts.

No provider-specific commercial/API contract is required to implement this internal baseline.

## Lender Adapter Boundary

The adapter baseline must remain provider-generic.

It may define:

- adapter protocol/interface;
- capability manifest;
- authenticated inbound-message result;
- normalized lender inbound-event contract;
- normalized reconciliation snapshot contract;
- normalized provider error classification;
- version identifiers for provider contract, adapter mapping, inbound normalization, and outbound mapping;
- secret-reference identifiers only, never secret values.

It must not:

- invent a real lender API;
- invent a real authentication scheme for a lender;
- store provider credentials in ordinary database records;
- claim provider certification;
- claim real provider connectivity.

## Supported Canonical Lender Events

The baseline must support exactly the accepted canonical lender event vocabulary required for the pilot:

- `LOAN_APPROVED`
- `LOAN_DISBURSED`
- `REPAYMENT_RECEIVED`
- `LOAN_DELINQUENT`
- `LOAN_SETTLED`
- `LOAN_CORRECTED`

Provider-specific source statuses are mapped behind a versioned adapter mapping and never passed directly into domain logic.

## Authentication Boundary

An inbound lender fact may enter the Badban inbox/domain path only after the adapter returns an authenticated/verified normalized message.

Authentication implementation remains adapter-specific.

The baseline must expose the boundary and prove through tests that unauthenticated/failed-verification payloads cannot create business inbox events.

No fake credentials or fake production verifier are authorized.

## External Loan Mirror Boundary

BL-025 may create and maintain the lender-authoritative mirror from authenticated normalized lender facts.

The mirror owns:

- lender/provider ID;
- external loan ID;
- optional GuaranteeCase linkage where a valid link already exists;
- original principal;
- outstanding principal;
- currency;
- provider-authoritative loan state;
- disbursement timestamp when reported;
- settlement timestamp when reported;
- delinquency state when applicable;
- last provider event time;
- synchronization/reconciliation freshness state;
- version.

Historical provider facts are preserved in append-only ExternalLoanEvent records.

## BL-026 Boundary

**BL-026 — Activate Guaranteed External Loan is NOT authorized by this decision.**

Therefore Sprint 13 must not:

- move GuaranteeCase to ACTIVE;
- move BackingAllocation RESERVED → ENCUMBERED;
- assert that a lender disbursement activated a guarantee;
- perform the one-to-one `External Loan Principal = Issued Guarantee Amount` activation transaction;
- create guarantee activation journal/control effects.

A `LOAN_DISBURSED` fact may be mirrored as lender-authoritative evidence, but Guarantee activation remains a later explicit command under BL-026.

## State and Correction Rules

External lender state is authoritative input, not locally invented state.

Rules:

- duplicate provider events never duplicate history/business effect;
- older events must not silently regress current mirror state;
- material corrections are append-only correction facts plus explicit current-state update;
- current state must preserve the last accepted provider event time;
- an event sequence gap, when sequence is supplied by the adapter contract, fails closed rather than guessing missing events;
- outstanding principal never becomes negative;
- exact decimals are required;
- no binary float.

## External Loan Creation Boundary

A mirror may be created only from a lender event that contains the minimum authoritative identity and monetary fields required by Technical 09.

Sprint 13 must not fabricate a GuaranteeCase linkage.

If a normalized lender event does not include or resolve a valid Badban GuaranteeCase reference, the mirror may remain unlinked where the accepted persistence model permits; later activation/linkage remains an explicit domain workflow.

If the repository schema or accepted contract requires a non-null GuaranteeCase link, then implementation must fail closed and must not invent one.

## Inbox / Idempotency

Authenticated normalized lender events must use the existing BL-041 inbox boundary.

Deduplication identity remains provider/source + event type + external event ID.

Same identity + same payload is a safe duplicate.

Same identity + changed payload fails closed.

The normalized provider event history also has provider-event uniqueness so replay cannot duplicate mirror effects.

## Reconciliation Snapshot Path

The lender adapter baseline must define and test a normalized reconciliation snapshot result containing at least:

- provider ID;
- snapshot timestamp;
- provider/source reference or evidence reference;
- authoritative loan records/current states required by Technical 09.

This Sprint does not implement BL-042 comparison/case workflow.

It only supplies the adapter-side normalized snapshot path needed by reconciliation later.

## API Boundary

Technical 07 defines:

- `POST /api/v1/integrations/lenders/{provider_id}/events`
- `GET /api/v1/external-loans/{id}`

Sprint 13 may implement these only within the following boundary:

### Lender event endpoint

The public/provider-scoped ingestion endpoint is authorized only if it is wired through a real adapter authentication abstraction and cannot accept unauthenticated caller-supplied normalized facts as trusted input.

If there is no concrete provider verifier configured, the endpoint must fail closed rather than provide a development bypass.

No generic unauthenticated event injection endpoint is allowed.

### External-loan query

The read endpoint may expose only normalized mirror state and reconciliation freshness.

It must identify the lender/provider of record and expose no provider credential or secret reference value that would itself grant access.

## Provider Lifecycle

Creating a lender mirror does not activate a provider.

Technical implementation/certification does not change provider lifecycle.

Provider ACTIVE/SUSPENDED/EXPIRED rules remain governed by the existing provider registry and legal authorization controls.

## Explicit Non-Goals

No BL-020, BL-021, BL-022, BL-023, BL-026, BL-027, BL-028, BL-029, BL-033, BL-034, BL-042, real lender integration, real lender credentials, provider certification, guarantee activation, repayment financial effect, exposure reduction, Stage pass, QA pass, Release Approval, Production, or real-money behavior.

## Stage Boundary

Decision 0033 remains active and has reactivated Stage/QA/Release gates.

Sprint 13 itself does not claim Stage, QA, Release Approval, or Production.

## Approval Effect

Code is authorized only for BL-024 and BL-025 within this Sprint 13 boundary.
