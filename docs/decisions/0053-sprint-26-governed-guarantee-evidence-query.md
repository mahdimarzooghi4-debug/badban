# Decision 0053 — Sprint 26 Governed Guarantee Evidence Query

- **Status:** Accepted — read-only backend enabler, no financial activation
- **Date:** 2026-10-09
- **Parent:** Technical 07 Query Contracts and Technical 11 Scoped RBAC
- **Dependency:** Sprint 25 request-bound evidence, PR #28 merged into PR #27; merge-branch CI #420 green

## Scope

Expose existing persisted guarantee details via `GET /api/v1/guarantees/{id}`,
and existing read-only Sprint 25 REQUESTED evidence projection via
`GET /api/v1/guarantees/{id}/request-evidence`. Both are scoped **staff read
ports**, not the complete BL-045 Guarantee Operations Workspace. No arbitrary
frontend-supplied program reference selects or widens the access scope.

Authorization: only active human OPERATIONS, RISK, FINANCE_RECONCILIATION,
or AUDITOR role in the guarantee's actual Program, or an eligible GLOBAL
grant, may inspect. Participant, unrelated Program role and any anonymous
identity are forbidden. Detailed guarantee state may be inspected regardless
of state; REQUESTED-specific source evidence denies transitioned cases and
contradictory source lineage, rather than adapting an incomplete snapshot.

Response is a typed OpenAPI contract using exact decimal strings, full
captured product/provider version and status, positions and observation
lineage, no provider secrets and no derived actions or eligibility. A
fingerprint is observed-data equality evidence only; not signed, validated
valuation, capacity, risk PASS, legal approval or backing lock.

## Non-goals

No reservation, loan activation, claims, payments, state changes,
public participant data, UI, selection/eligibility/risk rules,
provider integrations, additional schema or migrations. This
does **not** unblock BL-016/020/021/023/026/033/034/038/045/047/052.

PR remains Draft/Open pending explicit authorization to merge;
no Stage, QA, Release, Production or real money.
