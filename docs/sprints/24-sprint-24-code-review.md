# Sprint 24 — Technical Code Review Record

- **Status:** Technical Code Review Complete — human release review not implied
- **Date:** 2026-10-09
- **Scope:** read-only BL-020 multi-asset source inventory foundation
- **PR:** #27 — Draft/Open
- **Base:** Sprint 23 / PR #26
- **Reviewed code HEAD:** `b6dfbc605954ed125df42c88614e3106f3dacd0e`
- **Code CI Evidence:** #413 — SUCCESS

## Contract Verification

- Inventory reads one episode, all its AssetPositions, matching AssetTypes,
  and *all* persisted ValuationObservations in one PostgreSQL SELECT statement.
  No independent sequential reads are assumed to be transactionally atomic.
- Typed immutable records preserve position/type/episode version, actual
  ownership/funding, owner/custodian, quantity/unit, source lineage, and
  historical valuation observations.
- Every observation remains a separate observed fact. Stored freshness state
  and valid-until are reported, not reinterpreted as a usable valuation.
- Deterministic UUID/time sorting and canonical hash create a stable source
  inventory fingerprint. Fingerprint is **not** evidence authorization,
  concurrency lock, signed provider truth or an allocation decision.
- Missing valuation is an empty history, never a default zero/valid price.
- Cross-program/episode, participant-owner and unit-integrity mismatches
  fail closed. Non-approved asset states are displayed as observations only,
  never deemed eligible.
- No Gold special casing and no new numeric capacity, reserve/expiry policy,
  risk PASS, AssetAllocation/BackingAllocation, guarantee transition,
  Journal effect, provider integration or HTTP API.

## Tests and Review Findings

Four PostgreSQL-backed regression tests cover:

1. Two distinct AssetTypes/AssetPositions with different ownership and
   complete actual valuation history; unvalued sources stay unvalued.
2. Missing episode and cross-program access fail closed.
3. Source fingerprint changes when actual persisted source quantity changes.
4. A real second Program on an AssetPosition is rejected as inconsistent with
   its ParticipationEpisode, rather than accepted silently.

**CI #411:** Ruff format reported one multiline ownership condition.
It was corrected in commit `6c86bbc7418a2e2ddd709f793598c3c562e938b4`.

**CI #412:** Three tests passed; fourth failed because the negative fixture
assigned a random *nonexistent* program UUID, so the database FK rejected it
before reaching the application invariant. The test now creates a real second
Program and verifies the intended fail-closed domain behavior. This fix is
commit `b6dfbc605954ed125df42c88614e3106f3dacd0e`.

**CI #413:** full SUCCESS for Secret Scan and Quality jobs, including Ruff
format/lint, type check, migrations/drift, integration tests, dependency audit
and container build. No unreviewed code change remains after this code CI.

## Security and Future Integration Boundary

The entrypoint is an **internal** application read primitive, not an
authenticated/public endpoint. A later exposing caller must enforce
program/participant authorization and avoid leaking the raw source facts.
This review does not approve such an endpoint.

This projection does not prove source eligibility, lock a source, compute
available capacity, validate the risk snapshot, authorize expiry, or permit
REQUESTED to RESERVED. BL-020 decisions listed in
`docs/product-backlog/06-bl020-contract-dossier-2026-10-09.md` remain open.

Decision 0033 superseded the historic Stage deferral, but **Stage itself**
has not been executed or explicitly authorized for this PR. No independent
security or Release Approval is claimed.

## Gate Result

`Code = COMPLETE`

`Technical Code Review = COMPLETE`

`Merge / Stage / QA / Release / Production = NOT AUTHORIZED`
