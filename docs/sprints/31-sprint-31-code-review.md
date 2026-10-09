# Sprint 31 — Technical Code Review (BL-044 Audit Read APIs)

- **Date:** 2026-10-09
- **Reviewed Code HEAD:** `a4e362c18407ae3ad67a607e6eace01a7e0af140`
- **Code CI:** [#451](https://github.com/mahdimarzooghi4-debug/badban/actions/runs/37927407848) SUCCESS — 320 tests passed, 1 warning; Format, Lint, Pyright, PostgreSQL migrations/drift, Dependency Audit, Container Build and Secret Scan SUCCESS
- **Status:** Automated technical Code Review COMPLETE; Draft PR / human merge approval still required
- **Dependency:** PR #33 Draft/Open, CI #448 SUCCESS; no main merge

## Invariant review

1. **Read-only boundary:** new endpoints use SELECT only. No journal/guarantee/backing/risk/exposure transition, arbitrary audit mutation, or provider request. Existing `append_audit` remains the only new-audit source (denied access may legitimately add a denial audit through central authorization).
2. **Authorization:** requires active `AUDITOR` role and human principal via existing central authorization. Without `program_id`, only GLOBAL grant authorizes. With `program_id`, a matching Program grant or GLOBAL grant authorizes, but SQL filters the exact stored Program scope. No actor/aggregate inference for unscoped legacy records.
3. **Confidentiality:** response model allowlists provenance and timing metadata only; previous/new JSON and arbitrary scope JSON are not mapped or returned. Evidence references are opaque; evidence contents/provider payloads and secrets are not included.
4. **Cursor correctness:** lexicographic `(occurred_at,id)` order is deterministic. Cursor anchor must exist in the entire *authorized and filtered* stream (including exact scope, aggregate/action/correlation filters). Missing or foreign cursor returns 422; bounded page max is 100.
5. **Backward compatibility:** two additive GET routes on existing accepted `/api/v1/audit` contract. No schema migration, no changes to persisted event shape, no policy defaults, no new credentials.
6. **Tests:** OpenAPI read-only/schema assertions, PostgreSQL Program isolation, Global-only access for unscoped history, cursor cross-Program and cross-filter denial, correlation and aggregate selection, payload omission, 401/403, revoked grant and service-identity denial. Test suite successfully completed on the reviewed SHA.

## Risks, limits and honest qualification

- Audit scope is based on *persisted server-authored audit tags*. Existing unscoped rows intentionally remain inaccessible to Program-only auditors; no inferred scope/backfill is invented.
- GLOBAL AUDITOR can read metadata across Programs by accepted authorization contract; it is a privileged grant that must be operationally governed.
- This is an audit **metadata** explorer, not an evidence-content retrieval interface or a financial dispute-resolution decision.
- One test-suite warning reported by pytest does not represent a failing test; no assertion of zero warnings.
- This is an automated technical review, **not** independent human signoff, Stage QA, release authorization, or Production verification.
- After adding this review record, final HEAD requires another exact-SHA CI pass; the #451 success belongs only to the reviewed code HEAD.

## Disposition

**Technical Code Review complete for defined bounded scope.**
No identified blocking code invariant violation after CI #451. Keep PR Draft/Open,
no merge, no Stage/QA/Release/Production, and keep Figma paused.
