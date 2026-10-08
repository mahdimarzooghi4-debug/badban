# Sprint 16 — Reconciliation Blocks and Resolution Workflow Core

- **Status:** Accepted / Code Authorized
- **Date:** 2026-10-08
- **Stage:** Sprint
- **Scope:** backend-first / BL-043 core
- **Base Dependency:** Sprint 14 BL-042 Code + Code Review complete on PR #17
- **Branch Strategy:** stacked on `sprint-14-reconciliation-engine-core` until PR #17 is explicitly merged
- **Traceability:** Technical 10 §§9-10, 24-29, 35-37
- **Code Authorization:** GRANTED BY DECISION 0042

## 1. Sprint Goal

Implement the governed reconciliation blocking projection and resolution workflow required by BL-043 without inventing command-block mappings, resolution authority, numeric thresholds, direct repair behavior, or financial-state mutation.

## 2. Governed Blocking Matrix

Blocking behavior must come only from the exact `RECONCILIATION_POLICY` version already bound to the reconciliation case/run.

The policy representation may carry an explicit blocking matrix that maps:

- reconciliation reason/type;
- materiality;
- blocked command type;
- resource type/scope.

Rules:

- no built-in production mapping;
- no implicit latest policy;
- no inferred block from provider name;
- missing/invalid required blocking rule fails closed for commands that require the gate;
- INFO/WARNING do not become MATERIAL/CRITICAL by code;
- the hard loan/guarantee principal invariant remains CRITICAL.

## 3. Reconciliation Block Projection

Authorized persistence may add the Technical 10 `reconciliation_blocks` projection with:

- id;
- reconciliation_case_id;
- blocked_command_type;
- resource_type;
- resource_id/scope reference where applicable;
- active;
- activated_at;
- cleared_at;
- exact policy/rule lineage.

Blocks are derived/current control projections from unresolved cases + explicit governed policy.

They are not independent business truth and cannot outlive the unresolved case/policy conditions that created them.

## 4. Resolution Workflow

Authorized resolution categories are exactly:

- `INTERNAL_CORRECTION`
- `EXTERNAL_CORRECTION`
- `LATE_EVENT_APPLIED`
- `MAPPING_CORRECTION`
- `ACCEPTED_DIFFERENCE`
- `DISPUTE_OUTCOME`

Resolution workflow may implement:

- proposal;
- evidence/reason capture;
- optional correction-command references;
- review/approval;
- recheck;
- case transition to DISPUTED/RESOLVED only through accepted workflow;
- clearing derived blocks only after valid resolution/recheck conditions.

Original observations remain immutable.

## 5. Maker-Checker

For MATERIAL/CRITICAL resolution, proposer and approver must be different when approval is required by the exact governed policy.

The approval must bind to the exact:

- reconciliation case;
- proposal payload;
- resolution type;
- evidence references;
- expected case version/state;
- policy lineage.

Stale/changed proposal approval fails closed.

No self-approval.

## 6. Pre-Command Gate

Authorized application service may expose a deterministic read/check such as:

`assert_reconciliation_command_allowed(...)`

It may evaluate:

- reconciliation type;
- command type;
- resource;
- active blocks;
- case status;
- freshness/materiality already established by governed reconciliation evidence.

Failure returns stable reconciliation control errors such as:

- `RECONCILIATION_BLOCK`
- `EXTERNAL_STATE_STALE`

Sprint 16 does not wire this gate into future commands that do not yet exist.

## 7. APIs

Technical 10 endpoints authorized in this Sprint:

- `POST /api/v1/reconciliation/cases/{id}/propose-resolution`
- `POST /api/v1/reconciliation/cases/{id}/approve-resolution`
- `POST /api/v1/reconciliation/cases/{id}/recheck`

Existing Sprint 14 run/case reads remain unchanged.

There is no generic "mark matched" or direct-state-edit endpoint.

## 8. Audit and Events

Resolution/block transitions must produce audit and transactional outbox evidence.

Authorized events:

- `ReconciliationResolutionProposed`
- `ReconciliationResolved`
- `ReconciliationBlockActivated`
- `ReconciliationBlockCleared`

Events never authorize financial mutation by themselves.

## 9. Explicit Non-Goals

Sprint 16 does not implement:

- BL-020 reservation;
- BL-021 expiry;
- BL-023 legal guarantee issuance;
- BL-026 activation;
- BL-027 repayment effects;
- BL-033 reserve operations;
- BL-034 delinquency processing;
- claim settlement/recovery;
- participant exit;
- direct journal/balance repair;
- direct GuaranteeCase/BackingAllocation mutation;
- provider-specific blocking defaults;
- Stage/QA/Release/Production;
- real-money behavior.

## 10. Test Contract

Tests must cover at least:

- explicit policy mapping activates a block;
- missing/invalid mapping fails closed where a command requires reconciliation gating;
- unresolved MATERIAL/CRITICAL case can block an explicitly mapped command/resource;
- unrelated command/resource is not blocked without explicit policy mapping;
- proposal requires reason/evidence;
- resolution type outside the canonical set fails closed;
- proposer cannot self-approve when maker-checker applies;
- stale case/proposal version approval fails closed;
- resolution preserves original observations;
- valid resolution/recheck clears derived block;
- duplicate proposal/approval/recheck is idempotent;
- no resolution path directly mutates journal or unrelated domain financial state.

## 11. Delivery Boundary

Sprint 16 ends at Code + Code Review for the authorized BL-043 core.

While PR #17 remains unmerged, Sprint 16 is stacked on the Sprint 14 branch. It must not be merged to `main` ahead of its prerequisite.

Any Sprint 16 PR must remain Draft/Open through Code Review and must not be merged without explicit user instruction.
