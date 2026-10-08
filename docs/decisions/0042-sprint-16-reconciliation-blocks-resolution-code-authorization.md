# Decision 0042 — Sprint 16 Reconciliation Blocks and Resolution Workflow Core; Code Authorization

- **Status:** Accepted
- **Date:** 2026-10-08
- **Scope:** Sprint 16 / BL-043 Core / Code Authorization
- **Depends on:** BL-008; Sprint 14 BL-042 Code + Code Review complete; Technical 10 §§9-10,24-29,35-37
- **Authorizes:** BL-043 core only

## Decision

Accept Sprint 16 and authorize Code for the governed reconciliation blocking projection and resolution workflow defined by BL-043.

Sprint 16 is intentionally stacked on the Code-Reviewed Sprint 14 branch while PR #17 remains unmerged. This dependency does not authorize merging either PR.

## Governed Blocking Rule

Blocking is policy-driven.

The exact `RECONCILIATION_POLICY` bound to the case/run must explicitly provide any mismatch/materiality → blocked-command/resource mapping required by the workflow.

The implementation must not:

- invent default production blocking mappings;
- infer mappings from provider names;
- silently treat missing mapping as permission;
- downgrade the hard loan/guarantee principal invariant from CRITICAL;
- invent numeric materiality thresholds.

Where a command declares reconciliation gating as required and the governing rule is missing/invalid, the command gate fails closed.

## Reconciliation Blocks

Sprint 16 may add the Technical 10 `reconciliation_blocks` derived/current projection.

A block must retain lineage to:

- reconciliation case;
- exact governed rule/policy;
- blocked command type;
- affected resource/scope;
- activation and clearing state/timestamps.

A block cannot directly mutate the financial/domain aggregate it protects.

## Canonical Resolution Types

Only these resolution types are authorized:

- `INTERNAL_CORRECTION`
- `EXTERNAL_CORRECTION`
- `LATE_EVENT_APPLIED`
- `MAPPING_CORRECTION`
- `ACCEPTED_DIFFERENCE`
- `DISPUTE_OUTCOME`

A resolution may reference a normal correction/domain command, but the reconciliation workflow itself must never repair balances, journal history, GuaranteeCase state, BackingAllocation state, or provider mirror history by direct row edit.

## Maker-Checker and Stale Safety

Material/critical resolution must support accountable maker-checker under the exact governed policy.

Where approval is required:

- proposer != approver;
- approval binds to exact proposal payload/hash;
- approval binds to exact case version/state and policy lineage;
- changed/stale proposal fails closed;
- reason and evidence are mandatory.

No self-approval.

## Resolution and Recheck

A case may become DISPUTED or RESOLVED only through the controlled workflow.

Resolution does not erase or rewrite original mismatch observations.

Clearing a derived block requires accepted resolution/recheck conditions; no generic manual "clear block" or "mark matched" operation is authorized.

## Pre-Command Gate

Sprint 16 may expose a reusable application-level reconciliation gate for current/future commands.

It may return:

- `RECONCILIATION_BLOCK`
- `EXTERNAL_STATE_STALE`

based only on explicit active block/evidence/policy state.

This decision does not authorize wiring the gate into business commands that are not yet implemented or not otherwise authorized.

## API Authorization

Authorized mutation APIs are limited to the Technical 10 workflow:

- propose resolution;
- approve resolution;
- recheck.

No arbitrary reconciliation case status mutation endpoint is authorized.

## Audit / Outbox

Material block/resolution transitions must be auditable and may emit only accepted reconciliation events, including:

- `ReconciliationResolutionProposed`
- `ReconciliationResolved`
- `ReconciliationBlockActivated`
- `ReconciliationBlockCleared`

Events do not themselves authorize financial effects.

## Explicit Non-Goals

No BL-020, BL-021, BL-023, BL-026, BL-027, BL-033, BL-034, claim settlement, recovery, return allocation, participant exit, direct ledger repair, provider-specific default policy, Stage, QA/Testing, Release Approval, Production, or real-money behavior.

## Approval Effect

Code is authorized only for the Sprint 16 BL-043 core described above.

Sprint 16 must remain stacked on its Sprint 14 prerequisite until that prerequisite is explicitly merged. Any Sprint 16 PR remains Draft/Open through Code Review and must not be merged without explicit user instruction.
