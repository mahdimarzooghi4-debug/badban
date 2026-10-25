# BL-020 Decision-Ready Contract Dossier — Technical Review

## Addendum — 2026-10-25

Sprints 36–39 are now merged to `main` (final main CI #512 green). This completes the internal source-acquisition work but does not authorize BL-020 or establish that internal recorded valuation labels are independently verified external facts.

Previously confirmed product constraints: multi-lender and multi-asset operation; Direct Lending disabled; one supported Gold asset type; maker-checker; a 72-hour reservation duration; portfolio risk states GREEN/AMBER/RED. This dossier records that the duration is 72 hours from successful reservation in UTC; it does not define the allocation algorithm or qualifying risk semantics.

Still requiring explicit Business/Risk/Legal input before a reservation command can be implemented:

- deterministic asset-position selection/order and whether a single reservation may split across positions with different owners or funding types;
- canonical sources for active restrictions, holds, prior allocations and legal encumbrance; unknown/unavailable external facts remain fail-closed;
- which risk states qualify for a new reservation, including AMBER treatment, and required snapshot scope/freshness/recheck semantics;
- accepted valuation/provider/legal evidence needed to treat stored observations as eligible.

Concurrency locking, idempotency, transaction shape, audit/outbox atomicity and rollback behavior remain engineering contracts to implement after those inputs are fixed. BL-020 remains blocked; no financial mutation is authorized by this addendum.

- **Status:** BLOCKED / decision inputs required; no product Code Authorization
- **Date:** 2026-10-09
- **Repository evidence:** Technical 03/04/06/07; Decisions 0003/0008/0010;
  Sprint 09 risk, Sprint 05 capacity, Sprint 24 read-only inventory

## 1. Exact source state already available

- `ParticipationEpisode` binds participant/program.
- `AssetPosition` binds episode, program, type, ownership/funding, quantity,
  custody and aggregate version.
- `AssetType` binds configurable type, unit and version; Gold is not special.
- `ValuationObservation` stores immutable observations, source, observed/
  valid-until timestamps and persisted freshness status.
- `GuaranteeCase` can remain REQUESTED with nullable reserved amount, expiry,
  risk snapshot and policy pack ID.
- `PortfolioRiskSnapshot` is versioned policy-bound evidence, not a reservation
  command and not an implicit PASS.
- Sprint 24 **inventories** this source state only. An inventory fingerprint is
  not a replay-safe reservation claim.

## 2. Necessary explicit decisions, not assumed implementations

| Contract | Must be specified by accountable authority | Unsafe alternative |
| --- | --- | --- |
| Backing selection | Which and how many AssetPositions, stable allocation ordering, per-position capacity distribution, constraints on mixed ownership/funding | Choose first or largest position without approval |
| Restriction/exposure sources | Canonical active restrictions and holds, partial allocations, legal encumbrance state, capacity units | Default missing exposures or holds to zero |
| Expiry | 72 hours from successful reservation; persist and compare the resulting instant in UTC | Client controls expiry or derives it from local time |
| Risk gate | Matching policy scope, snapshot ID and age/freshness, risk state qualifying rule, recheck timing and source integrity | Implicit GREEN or stale risk PASS |
| Provider/legal/valuation | Current authorized product/legal/custody state, accepted valuation selection/correction/freshness | Use any historical observation as current |
| Concurrency | Which aggregate rows to lock and deterministic lock order; expected versions; idempotency replay scope | Race-prone read-then-write |
| Atomic outputs | Exact BackingAllocation schema/status, GuaranteeCase RESERVED, DecisionSnapshot/audit/outbox contents | Partial capacity hold or event emission |

## 3. Acceptance / rejection scenarios

**Positive scenario (only after approval):** one specific REQUESTED guarantee
bound to one approved pack, matching exact risk snapshot, accepted valuations,
authorized provider/legal state and deterministically selected/multi-asset
capacity. Lock and recheck all source versions. Atomically create allocations
and decision/audit/outbox with exact expiry; same request replay returns same
result.

**Negative cases:** missing/ambiguous policy, stale/missing valuation,
unqualified risk snapshot, insufficient capacity, bad ownership/custody,
unresolved blocking reconciliation, duplicate competing allocation, changed
source version, expired legal authorization, multi-asset mismatch, rollback
halfway through transaction. Every rejection must create **no reservation or
partial backing** and must not claim PASS.

## 4. Owners / unlock gate

Business/Risk/Legal must explicitly define and accept the missing allocation,
restriction/exposure-source, risk-qualification and evidence-acceptance decisions,
with source schema and versioning. Reservation duration is confirmed as 72 hours
from successful reservation and represented as a UTC instant.
Engineering then records matching Technical contract, Sprint authorization,
tests, implementation and code review before the first reservation command.

Until that gate, **BL-020 is NOT Code-ready**, and dependent BL-021/023/026
remain blocked. Stage is reauthorized by Decision 0033 as a process gate but
not executed by this document.

## 5. Sprint 25 evidence bridge (still read-only)

The one-statement internal request-bound evidence view can now retrieve the
exact REQUESTED GuaranteeCase, captured CreditProductVersion and its provider
plus all persisted episode backing/valuation sources together. It rejects
contradictory request/captured product or source lineage and carries a
deterministic observation fingerprint. This is *not* source qualification,
capacity reservation, a legal approval, a cryptographic source attestation,
a hold or a concurrency lock. Missing executable allocation, restriction/exposure sources, risk-gate qualification,
evidence acceptance and transaction definitions above continue to block BL-020.
