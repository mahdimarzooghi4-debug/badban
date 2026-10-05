# Badban Dependency Order and Sprint-Ready Delivery Slices

- **Status:** Proposed
- **Date:** 2026-10-05
- **Stage:** Scrum/Product Backlog
- **Scope:** bounded external-lender pilot
- **Depends on:** Ordered Product Backlog; Definition of Ready / Done
- **Sprint Authorization:** NOT YET GRANTED

## 1. Purpose

Translate the ordered backlog into coherent vertical delivery slices while preserving the parent process and Technical dependencies.

These are **candidate Sprint slices**, not approved Sprints.

A Sprint is selected only after Product Backlog stage completion and explicit Sprint planning.

## 2. Dependency Spine

The critical dependency spine is:

```
Implementation Stack
→ Persistence / Environment / CI
→ Identity / RBAC
→ Program / Participant
→ Asset Type / Asset Position
→ Valuation
→ Policy Runtime
→ Capacity
→ Provider / Product / Legal Authorization
→ Guarantee Request / Reservation
→ Guarantee Issuance
→ Lender Adapter / External Loan Mirror
→ Guarantee Activation
→ Repayment / Release
→ Claim / Recovery
→ Return / Entitlement / Exit
→ Reconciliation / Operational Workspaces
→ Recovery / Security / E2E Hardening
```

Cross-cutting capabilities such as outbox/inbox, audit, ledger, observability, and security are introduced before the first workflow that requires them rather than postponed to the end.

## 3. Slice 0 — Implementation Foundation

**Candidate items**

- BL-001 Implementation Stack Decision Pack
- BL-002 Repository and CI Quality-Gate Blueprint
- BL-003 Environment, Configuration, and Secret Boundary
- BL-004 Transactional Persistence and Migration Foundation
- BL-005 Observability and Correlation Foundation

**Outcome**

A Sprint can begin implementation with explicit technology choices and repository/runtime conventions rather than ad hoc decisions during coding.

**Sprint-ready when**

- stack choices required by selected code work are recorded;
- local/CI environment model is explicit;
- persistence/migration strategy is accepted;
- test/lint/type/security gates are known;
- no production deployment is implied.

**No business financial transaction is delivered by this slice.**

## 4. Slice 1 — Identity and Core Participant/Asset State

**Candidate items**

- BL-006 Central Identity Integration
- BL-007 RBAC and Scoped Authorization
- BL-009 Program and Participation Episode
- BL-010 Asset Type Registry
- BL-011 Asset Position and Ownership/Funding Classification
- BL-044 Audit and Evidence Trace baseline

**Outcome**

An authenticated, scoped operator can create and inspect program/participant/asset state with explicit participant-owned vs program-attributed classification.

**Acceptance journey**

```
Authenticated operator
→ authorized Program/Participation Episode
→ approved Asset Type reference
→ Asset Position
→ explicit ownership/funding classification
→ audit trail
```

**Must not yet claim**

- guarantee capacity;
- legal guarantee issuance;
- external loan;
- real-money settlement.

## 5. Slice 2 — Valuation, Policy, and Capacity

**Candidate items**

- BL-012 Immutable Valuation Observation
- BL-013 Policy Version and Policy Pack Lifecycle
- BL-014 PolicyResolver and DecisionSnapshot
- BL-015 Deterministic Guarantee Capacity Calculator
- BL-016 Guarantee Capacity Read Model
- BL-032 Portfolio Risk Snapshot and Gate baseline

**Outcome**

Badban can deterministically calculate and explain available guarantee capacity from accepted asset/valuation/policy inputs without reserving it.

**Acceptance journey**

```
Asset Position
→ Accepted Valuation
→ ACTIVE Policy Pack
→ Risk Snapshot
→ Deterministic Capacity
→ Read Model with freshness/version evidence
```

**Hard proof**

Same captured inputs + same policy/algorithm versions reproduce the same result.

## 6. Slice 3 — Provider/Legal Registry and Guarantee Reservation

**Candidate items**

- BL-008 Maker-Checker / ApprovalRequest baseline
- BL-017 Credit Provider and Product Version Registry
- BL-018 Legal Entity Role and Authorization Registry
- BL-019 Guarantee Request Aggregate Path
- BL-020 Atomic Backing Reservation
- BL-021 Reservation Expiry
- BL-041 Transactional Outbox / Inbox baseline

**Outcome**

An authorized operator can request and atomically reserve guarantee capacity against exact backing without double reservation.

**Acceptance journey**

```
Eligible Participation
+ Capacity
+ Provider/Product
+ Legal Authorization
+ Risk Pass
→ Guarantee REQUESTED
→ RESERVED
→ exact BackingAllocation
→ DecisionSnapshot / Audit / Outbox
```

**Negative acceptance**

- stale valuation blocks;
- insufficient capacity blocks;
- RED risk blocks;
- invalid provider/legal authorization blocks;
- concurrent duplicate reservation cannot exceed capacity;
- expiry releases once.

## 7. Slice 4 — Legal Guarantee Issuance

**Candidate items**

- BL-022 Guarantee Issuer Adapter Baseline
- BL-023 Confirm Legal Guarantee Issuance
- BL-048 relevant provider-security controls

**Outcome**

A RESERVED case can become ISSUED only when authoritative legal guarantee evidence is received/verified through an authorized Guarantee Issuer path.

**Acceptance journey**

```
RESERVED
→ provider/manual-adapter evidence
→ legal authorization VALID
→ external guarantee ID / amount / evidence
→ ISSUED
```

**Hard proof**

Internal reservation alone never creates ISSUED.

## 8. Slice 5 — External Lender Activation Golden Path

**Candidate items**

- BL-024 Lender Adapter Baseline
- BL-025 External Loan Mirror
- BL-026 Activate Guaranteed External Loan
- BL-042 lender/guarantee reconciliation baseline

**Outcome**

Badban can activate a guaranteed external loan from authoritative lender disbursement while preserving the one-to-one invariant.

**Acceptance journey**

```
ISSUED Guarantee
+ authenticated LOAN_DISBURSED
+ external loan ID
+ exact principal match
+ no blocking reconciliation
→ ExternalLoan ACTIVE
→ Guarantee ACTIVE
→ Backing ENCUMBERED
→ Audit / Outbox
```

**Hard proof**

```
External Loan Principal = Issued Guarantee Amount
```

Any mismatch produces no partial activation.

## 9. Slice 6 — Ledger and Financial-Control Baseline

**Candidate items**

- BL-030 Append-Only Journal Engine
- BL-031 Product Account Taxonomy and Posting Templates
- BL-033 Guarantee Reserve Control

**Outcome**

Badban has the monetary/control ledger foundation needed for later claim, recovery, return, entitlement, and settlement flows.

**Acceptance requirements**

- balanced exact-decimal journals;
- append-only posting/reversal;
- legal entity/economic owner dimensions;
- monetary vs memorandum vs external mirror separation;
- no fake Badban loan receivable for external lender loans.

This slice may be delivered before or in parallel with Slice 5 if dependency planning requires it, but must be Done before claim/return financial posting.

## 10. Slice 7 — Repayment, Exposure Reduction, and Closure

**Candidate items**

- BL-027 Process Lender Repayment
- BL-028 Declining Guarantee Exposure Reduction
- BL-029 Loan Settlement / Guarantee Release / Closure
- BL-042 repayment reconciliation expansion

**Outcome**

Authoritative lender repayment updates the loan mirror exactly once and, when allowed by captured product rule, releases guarantee exposure/backing.

**Acceptance journey**

```
ACTIVE
→ authenticated REPAYMENT_RECEIVED
→ outstanding principal reduced once
→ declining exposure/backing reduced if rule permits
→ authoritative settlement
→ RELEASED / CLOSED
```

**Negative acceptance**

Duplicate repayment cannot reduce exposure twice.

## 11. Slice 8 — Delinquency, Claim, Settlement, and Recovery

**Candidate items**

- BL-034 Delinquency Processing
- BL-035 Claim Submission and Review
- BL-036 Claim Settlement
- BL-037 Recovery Receipts and Allocation
- BL-043 Reconciliation Blocks and Resolution Workflow
- BL-008 maker-checker expansion for high-impact actions

**Outcome**

Badban can process the full exception path without confusing claim payment with final loss.

**Acceptance journey**

```
ACTIVE
→ DELINQUENT
→ ClaimSubmitted
→ Review
→ APPROVED
→ settlement evidence
→ ClaimPaid
→ RecoveryOpened
→ Recovery receipts/allocation
→ residual loss if any
→ closure
```

**Hard proof**

Claim settlement outflow, recovered amount, open recovery, and final residual loss reconcile.

## 12. Slice 9 — Return Allocation and Future Entitlement

**Candidate items**

- BL-038 Return Recognition and Allocation
- BL-039 Future Financial Entitlement
- BL-030/031 posting templates as required

**Outcome**

Recognized economic return can be allocated under immutable policy without treating principal as return.

**Acceptance journey**

```
Recognized Economic Return
→ Eligible Net Return
→ Reserve Allocation
→ Livelihood
→ Future Financial
→ Capital Growth
→ Social Reinvestment
→ Carry-Forward if allowed
```

**Hard proof**

Allocation balances completely and preserves participant/program ownership.

## 13. Slice 10 — Participant Exit and Recycling

**Candidate items**

- BL-040 Participant Exit and Financial Reconciliation
- BL-043 exit reconciliation blockers
- BL-047 participant summary expansion

**Outcome**

Program exit can complete without erasing unresolved financial obligations, and ownership/funding rules determine release vs recycling.

**Acceptance journey**

```
ACTIVE Participation Episode
→ EXIT_INITIATED
→ financial/reconciliation checklist
→ participant-owned release / program-attributed recycling
→ unresolved obligations preserved
→ FINALIZED only when allowed
```

## 14. Slice 11 — Operations and Participant Workspaces

**Candidate items**

- BL-045 Guarantee Operations Workspace
- BL-046 Finance / Reconciliation Operations Workspace
- BL-047 Participant Badban Summary

**Outcome**

Users can operate and understand the system through authorized read models without turning UI state into authoritative financial truth.

**Requirements**

- stale/block/freshness state visible;
- server controls allowed actions;
- participant view is self-scoped;
- finance/audit views expose evidence without arbitrary mutation.

## 15. Slice 12 — Operational Hardening and Recovery

**Candidate items**

- BL-048 Security Hardening and Secret Rotation Verification
- BL-049 Business Readiness / Stop Controls
- BL-050 Backup / Restore / Recovery Verification
- BL-051 Concurrency, Retry, and Failure-Injection Suite

**Outcome**

The pilot implementation is resilient to crashes, retries, provider outage, duplicate events, credential failure, and recovery scenarios without violating financial invariants.

**Acceptance requirements**

- stop controls tested;
- replay/duplicate tests green;
- provider UNKNOWN_OUTCOME tested;
- restore rehearsal performs post-restore financial/reconciliation verification;
- security boundary/rotation tests pass.

## 16. Slice 13 — End-to-End Bounded Pilot Golden Path

**Candidate item**

- BL-052 Bounded Pilot End-to-End Golden Path

**Outcome**

A non-real-money Stage-like environment proves the accepted pilot journeys across module boundaries.

### Happy path

```
Participant / Program
→ Asset
→ Valuation
→ Policy
→ Capacity
→ Request
→ Reservation
→ Legal Guarantee
→ Lender Disbursement
→ 1:1 Activation
→ Repayment
→ Release
→ Closure
→ Reconciliation / Audit
```

### Exception path

```
Delinquency
→ Claim
→ Settlement
→ Recovery
→ Residual Loss
→ Reconciliation / Closure
```

Passing this slice does not itself grant Production approval.

## 17. Parallelization Rules

Safe parallelization examples:

- identity and persistence foundations after stack decision;
- Asset Type Registry and Program/Participation after persistence/authorization model;
- provider adapter interface work can begin with canonical stubs once provider-neutral contracts are Ready;
- ledger engine can progress in parallel with external-loan golden path after persistence conventions are fixed;
- UI read models may follow stable API contracts before every downstream lifecycle is complete.

Unsafe parallelization examples:

- coding reservation before policy/capacity/concurrency contracts are Ready;
- coding activation before issuance + lender mirror + 1:1 invariant are implementable;
- coding claim settlement before journal/reserve/reconciliation requirements are Ready;
- coding exit finalization before obligations/reconciliation semantics are Ready.

## 18. First Sprint Selection Rule

The first Sprint must be selected from the earliest Ready slice(s), normally starting with Slice 0 and only combining Slice 1 work when dependencies are fully resolved.

Before Sprint authorization:

- Product Backlog documents must be Accepted;
- BL-001 stack choices required by the Sprint must be resolved or explicitly selected as the Sprint's discovery outcome;
- selected items must satisfy Definition of Ready;
- Sprint Goal and Sprint Backlog must be written;
- acceptance tests must be explicit.

## 19. No-Code Guard

This document orders future implementation work but does not authorize implementation.

Current process state remains:

```
Business ✓
→ Technical ✓
→ Scrum/Product Backlog (in progress)
→ Sprint (not yet authorized)
→ Code (not yet authorized)
```
