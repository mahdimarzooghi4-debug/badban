# Decision 0039 — Reconciliation Policy Runtime Binding and Sprint 14 BL-042 Code Authorization

- **Status:** Accepted
- **Date:** 2026-10-07
- **Scope:** Policy Runtime binding; conditional Sprint 14 Code authorization
- **Depends on:** Technical 06/10; BL-024; BL-025; BL-030; BL-041; BL-044
- **Authorizes:** BL-042 and the minimum Policy Runtime extension below, after DoR passes
- **Authority:** Explicit Product Owner instruction in the development handoff

## Ownership and selection

`RECONCILIATION_POLICY` is a distinct PolicyVersion category. Reconciliation rules
must not be stored in risk policy, provider configuration, constants, environment
variables, arbitrary configuration tables, or mutable run-request payloads.

Resolve the ACTIVE Pilot Policy Pack by the existing exact-scope/effective-time
contract first. Select reconciliation policy only from its immutable exact
`component_version_ids`. Do not select latest, fall back by code/date, use a global
default, or dynamically replace the pinned component.

The required reconciliation scope has `pilot_scope` and `reconciliation_type`.
Additional dimensions require an accepted domain/provider contract. The service
must derive scope from authenticated/domain context; arbitrary caller-selected
scope must not select a more permissive policy. Among pinned reconciliation
components, require exactly one match. Zero matches and ambiguous matches fail
closed with distinct errors.

Following explicit Product Owner delegation of the scope-source choice, the
initial lender path derives scope from exactly one effective ACTIVE provider-bound
pack with explicit `{pilot_scope, provider_id}`. The API takes only provider_id.
Zero matches and multiple pilot/program scopes fail closed; no global fallback or
caller-authored pilot_scope. Additional scope dimensions are rejected until a
supported contract exists. Unlinked mirrors need this same explicit binding.

## Approval and integrity

At Pilot Policy Pack approval/activation, reconciliation components must exist,
have the correct type, have reached an approved immutable state appropriate for
inclusion, have `approved_at` and `approved_by`, and have a payload hash equal to
the canonical payload hash. DRAFT and merely REVIEWED components cannot authorize
a run. Preserve existing pack maker-checker and lifecycle governance.

Harden validation only for reconciliation components; do not change unrelated
legacy component semantics. An approved component must be immutable for governed
use, including before its inclusion in an ACTIVE pack. Runtime must verify the
selected exact component's approval proof and payload integrity.

Later creation, activation or supersession of other components never rewrites an
ACTIVE pack or substitutes a newer component. Historical runs remain tied to the
exact version selected when they ran.

## Strict payload schema

Define a versioned strict schema with no executable expressions or generic
expression language. Canonical fields are code-owned and allowlisted.

The payload's `reconciliation_type` must agree with scope. Every rule has a stable
`rule_code`, canonical `field_code`, comparison mode, materiality, reason code,
and explicit blocking mapping where applicable.

Comparison modes are exactly:

- `EXACT`;
- `DECIMAL_EXACT`;
- `TOLERANCE_BASED`;
- `INFORMATIONAL`.

Only TOLERANCE_BASED may carry an explicit exact-decimal tolerance. A missing,
invalid or float tolerance fails validation. Other modes must not silently apply
tolerance. There is no universal tolerance or rounding rule.

Materiality is `INFO`, `WARNING`, `MATERIAL` or `CRITICAL`, from the pinned policy
except for accepted hard invariants. No numeric threshold is invented.

Source freshness must have a strict deterministic representation containing
explicit policy data. Missing required freshness fails closed. No universal
duration is defined. Provider silence and stale evidence never imply MATCHED.

Blocking maps explicit rule/mismatch/materiality conditions to explicit command
types. There is no broad block-everything fallback or ad-hoc application mapping.
A command requiring a blocking decision fails closed if that policy is missing.

## Run lineage and hard invariant

Persist at least:

- policy_pack_id and policy_pack_version;
- reconciliation_policy_version_id and its version_number;
- reconciliation policy payload_hash;
- rule schema/version identifier;
- algorithm code/version;
- source snapshot identities, cutoffs and evidence references.

For a one-to-one lender/guarantee relationship, an authoritative difference
between original external loan principal and issued guarantee amount is always
CRITICAL. Policy cannot downgrade this exact-decimal invariant. BL-042 detects
and records it; it does not activate a guarantee.

## Sprint boundary

Sprint 14 is intended to implement BL-042 plus this minimum Policy Runtime
extension after a repeated DoR. It may implement reconciliation run/case/
append-only observation persistence, minimal policy-derived blocking projection,
comparison, materiality, freshness, idempotency/concurrency, evidence, audit and
transactional outbox. Use the existing lender mirror and canonical snapshot port.

BL-042 owns run/read APIs from Technical 10. No generic mark-matched or direct
state mutation API is authorized. Full human proposal/approval/resolution/block
clearing remains BL-043. Repairs use normal domain commands, never direct edits
to journal, external event, audit or provider history.

BL-022, BL-020, BL-023, BL-026, repayment financial effects, guarantee issuance,
backing reservation/release, Stage, QA gate, Release, Production and UI remain
outside this authorization. PR #9 must remain untouched.

## No production configuration or automatic progression

Seed no production reconciliation values, provider schedules, tolerance,
freshness durations, numeric materiality thresholds or blocked-command matrix.
Explicit test-only policies and test-only snapshots are allowed. No fake runtime
provider or credential is allowed. Missing valid pinned policy fails closed.

The policy-binding decision is accepted. It does not itself establish DoR,
implementation, Code Review, CI success or production readiness. If another
genuine contract dependency remains unresolved, stop at that boundary and report
it. After implementation and green CI, review the exact HEAD and leave the PR
Draft/Open. Merge requires a separate explicit user instruction.
