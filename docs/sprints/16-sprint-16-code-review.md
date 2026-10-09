# Sprint 16 — Code Review Record

- **Status:** Code Review Complete / Merge Pending Explicit Approval
- **Date:** 2026-10-08
- **Scope:** BL-043 Reconciliation Blocks and Resolution Workflow Core
- **PR:** #19
- **Reviewed Head:** `bcd86977e07210a9f11ee4d7ea1aa82d7c14fa6d`
- **Base:** `sprint-14-reconciliation-engine-core`
- **CI Evidence:** #330 — SUCCESS

## Review Outcome

Sprint 16 Code Review is complete for the Decision 0042-authorized BL-043 core.

The reviewed implementation preserves the accepted governance boundaries:

- reconciliation blocks are derived only from explicit `RECONCILIATION_POLICY` blocking rules;
- no default command-block mapping exists;
- missing required mapping can fail closed;
- resolution types are limited to the Technical 10 canonical set;
- resolution proposals preserve exact case version, payload hash, policy lineage, evidence, and maker/checker identity;
- the existing `ApprovalRequest` governance model is reused rather than creating a parallel approval system;
- correction-based resolutions remain unresolved/blocked until an authoritative reconciliation recheck succeeds;
- original reconciliation observations remain append-only;
- reconciliation never directly mutates Journal, GuaranteeCase financial state, BackingAllocation, or other protected financial state.

## Scope-Lineage Finding Resolved

Final review identified a blocking lineage defect in recheck:

- `scope_reference` participated in the reconciliation source fingerprint;
- however it was not persisted on `ReconciliationRun`;
- the recheck API accepted a new caller-supplied `scope_reference`;
- therefore a case from one scope could theoretically be rechecked against another scope.

The fix:

- persists `ReconciliationRun.scope_reference`;
- exposes it in the read model;
- removes caller-controlled `scope_reference` from the recheck request;
- makes recheck reuse the original run's `scope_definition` and `scope_reference`;
- rejects attempted scope substitution;
- adds regression coverage that persists `scope-a`, rejects injected `scope-b`, and proves the adapter receives the original scope.

## Verification

At reviewed HEAD `bcd86977e07210a9f11ee4d7ea1aa82d7c14fa6d`:

- CI #330 succeeded;
- Format, Lint, Type Check, migrations, migration drift, tests, dependency audit, container build, and secret scan passed;
- policy-driven block activation is covered;
- maker-checker self-approval rejection is covered;
- immediate accepted resolution clears derived blocks without financial mutation;
- correction resolution requires authoritative recheck before clearing;
- recheck scope substitution is rejected;
- PR #19 remains Draft/Open;
- PR #19 remains stacked on Sprint 14 and must not merge ahead of PR #17;
- no Stage/QA/Release/Production is claimed.

## Gate Result

`Code Review = COMPLETE`

Merge remains pending explicit user authorization and prerequisite ordering.
