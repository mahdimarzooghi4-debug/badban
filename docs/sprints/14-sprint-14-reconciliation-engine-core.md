# Sprint 14 — Reconciliation Engine Core

- **Status:** Code implemented; final CI and exact-HEAD Code Review pending (not Done)
- **Date:** 2026-10-07
- **Scope:** BL-042 plus minimum Policy Runtime extension
- **Authorization:** Decision 0039 and explicit Product Owner scope-source delegation
- **Entry:** main 1578d98d9d2f79b63afbc7b090c4392628ddb9d8; CI #295 / 37643851891 SUCCESS

## Repeated Definition of Ready

BL-024/025 (Sprint 13), BL-030 (Sprint 08), BL-041 (Sprint 11) and BL-044
(Sprint 12) are merged foundations. Technical 04/06/07/08/09/10/11/12 define
persistence, policy governance, permission, snapshots, financial separation and
history safety. Decision 0039 resolves policy ownership, pinning and approval.
The Product Owner delegated the remaining scope-source choice to implementation.
DoR passes for the provider-neutral core and canonical lender path below.
No real provider certification or production configuration is an entry assumption.

## Trusted provider scope

The API accepts provider_id, never pilot_scope, policy IDs, rules or raw snapshots.
After scoped authorization, resolve exactly one effective ACTIVE Pilot Policy Pack
whose explicit scope is `{pilot_scope, provider_id}` for that provider. No match
fails closed. Multiple candidates (including multiple programs/pilots) fail as
ambiguous. Do not guess or collapse those scopes. Then invoke the existing exact
scope/effective-time pack resolver, and select the single pinned component whose
scope is that exact scope plus reconciliation_type. This is explicit provider/pilot
binding in existing governed Policy Runtime, not a second configuration system.
An unlinked ExternalLoanMirror may participate only under this explicit binding.
Additional program/legal dimensions require a subsequent explicit supported scope
contract; runtime rejects them instead of silently dropping them.

## Implementation boundary

- Add RECONCILIATION_POLICY type, strict versioned payload and approval proof.
- Protect approved reconciliation component content in DB as well as application.
- Preserve superseded/retired approved pinned versions without latest substitution.
- Persist final immutable Run records and immutable observations; Case and Block
  projections remain available for later BL-043, with no mutation API in this Sprint.
- Obtain independent normalized lender snapshots through the existing adapter port.
- Compare canonical loan IDs, original/outstanding principal, currency and state;
  preserve source cutoff, internal mirror identity/version and safe source evidence.
- Detect missing/duplicate records, stale/outage, incompatible cutoffs and exact
  original-principal/issued-guarantee mismatch. The latter remains CRITICAL.
- Compare configured fields using EXACT, DECIMAL_EXACT, TOLERANCE_BASED or INFORMATIONAL.
- Serialize provider runs with a transactional DB advisory lock and persist unique
  source/rule/internal-snapshot identity; changed semantic content conflicts.
- Atomically persist run/cases/observations/blocks/audit/outbox. No business repair.
- Expose authorized run/read APIs only.

The shared comparison vocabulary accommodates accepted other source domains;
only the existing lender snapshot acquisition path is executable in this Sprint.
Other provider adapters, cash/claim/exit workflows remain explicit dependencies of
later source-specific delivery; no external source or authority is fabricated.

## Policy schema v1

`schema_version = reconciliation-rules-v1`; `reconciliation_type`; nonempty rules;
freshness with explicit internal_max_age_seconds and external_max_age_seconds;
explicit freshness materiality/blocked_commands; explicit missing-record,
cutoff-mismatch and principal-invariant blocking maps. Rule codes/fields are unique,
fields and command types code-allowlisted; tolerance is decimal-string, allowed
only for TOLERANCE_BASED. No executable expressions or production seeds.

All age limits and classifications in tests are test-only. These fields define
configuration shape, not production values. Missing policy/freshness fails closed.
An internal provider fact later than the independent snapshot cutoff is an
incompatible-cutoff discrepancy, never a match. Future snapshot timestamps are
not trusted as fresh. Empty provider silence is not MATCHED.
Missing issued-amount evidence on a linked guarantee also cannot match; its
classification and blocks use the explicit missing-record policy mapping.
Run identity includes the freshness classification at evaluation time, so an
unchanged snapshot crossing its configured freshness boundary produces a new
STALE evaluation instead of reusing a formerly MATCHED result. An explicit
Idempotency-Key replay still returns the original request's historical result.

## APIs

- POST /api/v1/reconciliation/runs (provider_id, Idempotency-Key)
- GET /api/v1/reconciliation/runs/{id}
- GET /api/v1/reconciliation/cases (provider_id, bounded limit)
- GET /api/v1/reconciliation/cases/{id}

Run permission: FINANCE_RECONCILIATION at provider scope (or explicit GLOBAL grant).
Reads: FINANCE_RECONCILIATION/AUDITOR with matching scope. No mark-matched,
propose-resolution, approve-resolution, recheck or full human resolution API.

## Migration and validation

Revision 20261007_0015 extends only the policy type check and adds reconciliation
Run/Case/Observation/Block tables, unique identity, constraints and immutability
triggers. Downgrade refuses before removing any schema if governed reconciliation
policy rows exist; use forward correction rather than deleting approved history.
Empty/compatible schemas support downgrade and upgrade. Tests cover policy proof,
pinning, integrity, immutable history, comparison/negative paths, concurrency,
rollback, authorization and OpenAPI. Full CI and exact-HEAD review are required
before Done. Local checks do not substitute for GitHub CI or Code Review.

## Explicit exclusions

BL-043 full human resolution/block clearing, BL-022, BL-020/021/023/026+, direct
lending, journal/history mutation, backing change, guessed thresholds, real
provider/credentials, UI, Stage, QA gate, Release and Production. PR #9 untouched.
After green CI and review, leave the Sprint PR Draft/Open for explicit merge
instruction. Next roadmap item is BL-022 only after explicit Merge and green main.

## Multi-source continuation — Decision 0040

The later Product Owner continuation authorizes strict read-only ports for all
six accepted types within Sprint 14. Decision 0040 supersedes the lender-only
acquisition boundary above. Lender requests remain backward compatible. Legal
sources use current actual legal-role authorization and exact legal/role Pack
binding; LEDGER uses actual Program/legal-entity binding and POSTED journal truth.
No runtime source implementation is fabricated; registries start empty.

Additive migration 0016 makes provider identity nullable, adds exclusive typed
legal/program identity with real foreign keys and a constraint, and permits a
missing internal cutoff. Published 0015 is unchanged. No history is rewritten.

**Remaining acceptance blockers:** real internal settlement acquisition lacks
source/cash/reference/state/value-date mapping; collateral acquisition lacks
legal registration/backing identity. Both report SOURCE_UNAVAILABLE and retain
external-only discrepancies through executable canonical ports. Neither may
produce MATCHED until the owning domain supplies accepted internal contracts.
Issuer issue timestamp and custody controls not present in current rows remain
missing comparison evidence. Ledger MEMO directional balance semantics are not
defined; configured MEMO scope fails closed. These gaps are not provider credentials
or a requirement to implement BL-022 in this Sprint. BL-042 remains not Done.

## Multi-source local verification

355 tests passed (208 prior tests preserved, 147 added), Ruff format/lint and
Pyright passed, dependency audit found no known vulnerabilities. Migration
upgrade/downgrade/upgrade and drift checks passed on a separate scratch database;
a populated multi-source downgrade refusal is also tested. Integration validation
uses an isolated local PostgreSQL test database and the existing NATS service.
Reconciliation does not bypass history guards or mutate journal/domain rows.
The shared algorithm is version 2; historical version-1 runs are unchanged.
Final exact-HEAD CI/review evidence is recorded on PR #16 after completion.
The two internal acquisition contract gaps above remain backlog acceptance
blockers; neither the entire BL-042 item nor real-provider readiness is Done.
