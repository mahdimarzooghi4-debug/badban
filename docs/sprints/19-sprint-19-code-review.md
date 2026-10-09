# Sprint 19 — Code Review Record

- **Status:** Code Review Complete / Merge Pending Explicit Approval
- **Date:** 2026-10-09
- **Scope:** BL-046 Finance / Reconciliation Read Model Core
- **PR:** #22
- **Reviewed Head:** `89a39414e0c9642f21aefd2d440853bae00ab6a9`
- **Base:** `sprint-18-recovery-verification-core`
- **CI Evidence:** #368 — SUCCESS

## Review Outcome

Sprint 19 Code Review is complete for the Decision 0045-authorized backend read-model core.

The reviewed implementation preserves the accepted boundaries:

- existing reconciliation list/detail APIs remain canonical;
- existing finance journal list/detail/reversal APIs remain canonical and unchanged;
- no new persistence model or migration was introduced;
- no projection store or asynchronous read-model subsystem was invented;
- `age_seconds` is derived from authoritative `first_detected_at`;
- `last_observed_age_seconds` is derived from authoritative `last_observed_at`;
- both elapsed-time fields use one request-time UTC timestamp per response;
- negative elapsed time is clamped to zero rather than becoming a false negative age;
- `active_block_count` is read from active ReconciliationBlock rows only;
- list block counts are batch-read, avoiding per-case N+1 queries;
- block reads do not create, clear, resolve, or mutate reconciliation blocks;
- `min_age_seconds` now uses the same `first_detected_at` definition as the exposed case age;
- the pre-existing queue ordering by `created_at DESC, id DESC` is preserved;
- no freshness threshold, SLA, health score, materiality remapping, or escalation rule was introduced;
- provider/global reconciliation authorization behavior remains unchanged;
- provider-scoped reads cannot broaden into another provider scope;
- journal authorization and maker-checker reversal behavior remain unchanged;
- no UI/Figma/frontend work was introduced.

## Code Review Finding and Fix

Deep review found one backward-compatibility regression in the initial implementation:

- adding age semantics had also changed default queue ordering from `created_at` to `first_detected_at`.

Decision 0045 authorized age/filter additions but did not authorize changing queue ordering.

The implementation was corrected to preserve the existing ordering while keeping age/filter semantics on `first_detected_at`.

A regression test now proves that a change in `first_detected_at` does not reorder the existing queue contract.

## Verification Coverage

Tests cover:

- composed type/status/materiality/provider/minimum-age filters;
- age derived from `first_detected_at`;
- last-observed age derived from `last_observed_at`;
- active reconciliation block count;
- read-only preservation of active blocks;
- provider-scope authorization denial;
- preservation of existing queue ordering;
- OpenAPI exposure of the additive operational fields.

Existing Sprint 08 tests continue to cover:

- authorized finance/auditor journal reads;
- legal-entity scope isolation;
- AUDITOR reversal denial;
- maker-checker journal reversal;
- absence of arbitrary journal create API.

## Verification

At reviewed HEAD `89a39414e0c9642f21aefd2d440853bae00ab6a9`:

- CI #368 succeeded;
- Secret Scan, Format, Lint, Type Check, migrations, migration drift, tests, dependency audit, and container build passed;
- PR #22 remains Draft/Open;
- PR #22 remains stacked on Sprint 18;
- no Stage/QA/Release/Production is claimed.

## Delivery Boundary

The **backend read-model core** of BL-046 is complete.

The BL-046 UI workspace remains explicitly incomplete/out of scope for Sprint 19.

## Gate Result

`Code Review = COMPLETE`

Merge remains pending prerequisite ordering and explicit user authorization.
