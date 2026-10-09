# Sprint 26 — Technical Code Review

- **Status:** Technical Code Review COMPLETE; not an independent human approval
- **Date:** 2026-10-09
- **PR:** #29 (Draft/Open, stacked on PR #27)
- **Reviewed exact code HEAD:** `b961b185d6ca9e8c297c5487b9b35486fd2e8497`
- **Full code CI:** #426 — SUCCESS (Quality and Secret Scan)
- **Authorization:** Decision 0053 and accepted Technical 07/11 query/RBAC boundaries

## Scope Audited

- `GET /api/v1/guarantees/{guarantee_id}`: exact persisted GuaranteeCase,
  including raw state and requested/reserved/issued/exposure decimals. This
  endpoint never authorizes an action, computes capacity or changes financial state.
- `GET /api/v1/guarantees/{guarantee_id}/request-evidence`: typed observed
  lineage of REQUESTED guarantee, captured product/provider, episode and
  full multi-asset valuation source history. No declared eligibility, risk
  PASS, legal approval, allocation or reservation functionality.
- Pydantic schemas preserve UUIDs, integer versions, timestamps and exact
  decimal **strings**; DB NUMERIC scale is preserved, not rounded/recomputed.
- Both endpoints require authenticated, active human identity with a scoped
  OPERATIONS/RISK/FINANCE_RECONCILIATION/AUDITOR RoleGrant for the stored
  participation Program or an authorized global grant.
- Anonymous callers receive 401; other-program staff receive 403;
  missing guarantees receive 404. REQUESTED-only evidence refuses a
  transitioned GuaranteeCase with 409.

## Security Finding and Resolution

The initial request evidence application query read the episode program
without a database-side program-scope predicate. Although the route
pre-authorized a Program, the second read could have used session-cached ORM
identity fields if lineage changed across the requests. The reviewed code
now qualifies the second SQL select with
`ParticipationEpisode.program_id == program_id` and refreshes existing
identity-map state using `populate_existing=True`. If source reparenting
occurs across the reads, no cross-scope evidence is returned; cross-program
projections fail as NOT_FOUND. The source remains a read-only observation,
**not** a transaction lock or stable eligibility decision.

## Verified Regression Scope

Five new backend tests:

1. OpenAPI role, authentication/error and decimal-string contract.
2. Read detail/evidence for all four authorized staff roles, two asset
   positions (one not valued), and no new Journal, DecisionSnapshot or
   Outbox business effects.
3. Anonymous, wrong-program and missing-case access denials.
4. Persisted non-REQUESTED state visible in detail but explicitly rejected
   by request-only evidence.
5. Evidence fingerprint changes with real AssetPosition quantity update.

Pre-existing Sprint 24/25 lineage tests remain in full regression.

## CI Failure Resolution

- #421: Ruff formatting in new regression fixture only — fixed.
- #422: Ruff alias import sorting — fixed.
- #423: Pyright detected improper async-generator tuple construction in
  regression counts — fixed.
- #424: test expected a short money string, while NUMERIC(38,18)
  legitimately returned a scale-preserving exact string; test now compares
  exact Decimal numeric value, without casting to float or changing API data.
- #425: complete code CI SUCCESS prior to security review improvement.
- #426: complete code CI SUCCESS after database-side Program binding.

## Remaining Backend Blockers

- BL-020 multi-asset selection/hold/locking, expiry and risk qualification
  have no accepted executable business/legal/risk decision.
- BL-016/021/023/026 and repayment/closure/claim/recovery/returns depend on
  those blocked real transitions and external authoritative source evidence.
- BL-033 reserve production definitions and BL-034 delinquency product
  rule schema require separate accepted decisions. No default rule/PASS.
- The full BL-045 workspace, participant BL-047 and BL-052 golden path
  are NOT complete.
- Provider/legal/custody/settlement naming, live credentials, integration,
  recovery, Stage, QA, Release and Production still need separate gates.
  No synthetic credentials or live financial activity were introduced.

## Gate Record

`Code = COMPLETE`

`Technical Code Review = COMPLETE`

`Feature scope = read-only evidence API, not full Backend completion`

`Merge / Stage / QA / Release / Production = NOT AUTHORIZED`
