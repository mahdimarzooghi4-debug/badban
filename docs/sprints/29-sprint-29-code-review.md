# Sprint 29 — Technical Code Review

- **Status:** Technical Code Review COMPLETE; not an independent human approval
- **Date:** 2026-10-09
- **PR:** #32 Draft/Open, stacked on Sprint 28 PR #31
- **Reviewed exact code HEAD:** `8a9db081ba17860ed3c9e9851f7835757aca9147`
- **Code CI #444:** SUCCESS (314 tests passed, 1 existing warning, Quality and Secret Scan passed)
- **Parent contracts:** Technical 07 §21, Technical 08 §§8-11, 13, 15, 24-26, 29, Technical 11 Provider-scoped RBAC

## Reviewed Backend Changes

1. `GET /api/v1/external-loans/{loan_id}/events` only reads normalized
   persisted `ExternalLoanEvent` records, never raw provider payload or
   financial commands. Authenticates an active Badban human identity and
   delegates Provider/GLOBAL grant checking to the same shared
   `_authorize_read` that protects the underlying ExternalLoanMirror.
2. SQL always binds `external_loan_mirror_id == loan_id`. The immutable
   event cursor must exist on the **same** mirror. Cross-loan or forged
   cursor errors are 422, not unrelated records. A bounded
   `limit <= 100` and `limit+1` detection avoid unbounded result sets.
   Deterministic ordering uses `(provider_event_at, id)`, with
   lexicographic SQL tuple keyset continuation. This follows provider
   observation time, not guaranteed transport arrival order.
3. `GET /api/v1/external-loans/{loan_id}/events/{event_id}` first authorizes
   the same mirror and then reads only the event attached to it.
   Cross-loan detail is 404; anonymous is 401; missing active grant 403.
4. Original event facts remain independent: `APPLIED`, `STALE`,
   `HISTORY_ONLY`, and `CORRECTED` are exposed **verbatim**, not
   upgraded to financial eligibility or borrower repayment command.
   `principal_delta` and `outstanding_principal_reported` preserve
   PostgreSQL NUMERIC precision and sign as decimal strings, never float.
5. Immutable digest and original evidence references, provider contract,
   adapter mapping, inbound normalization and provider event sequence
   stay visible to the authorized reviewer without exposing provider
   secrets or raw lender request data.

## Authorization Mutation Review

The initial scenario denied an actor with no grant. Technical review
strengthened it to cover an actor with a **real active role grant to an
independent second CreditProvider**: that actor reads their own
provider's empty history but receives 403 for the first provider; the
first provider's auditor likewise cannot read the second. Revoked role
grants deny the next request. These are DB-backed PostgreSQL tests,
not UI-only checks.

## Tests and CI Trace

- New OpenAPI read-only, error and exact decimal schema test.
- New multi-event integration scenario exercises mixed APPLIED/CORRECTED/
  STALE, 2-record pagination across five observations, event detail,
  source lineage, decimal precision, real second-provider grant,
  unauthorized access, nonexistent loan, invalid limits, foreign cursor,
  cross-loan detail and guarantee/journal non-mutation.
- New empty-history and revoked-role tests.
- #440: Ruff formatting only, corrected.
- #441: Ruff unnecessary f-string, corrected.
- #442: Pyright `dict[str, object]` HTTP params annotation, corrected
  using `dict[str, str | int]`.
- #443: full CI SUCCESS before the explicit cross-provider review test.
- #444: **final reviewed code CI SUCCESS**, 314 passed, Quality + Secret
  Scan successful. No unexpected business write or Stage action.

## Boundary / Incomplete Work

This is **evidence accessibility**, not proof of independent provider
trust or an accepted commercial/financial event:
- Provider adapters/authentication and normalized inbox were previously
  built; real credential trust and provider integrations remain external.
- Seeing `REPAYMENT_RECEIVED` does **not** mutate GuaranteeCase,
  journal, exposure, backing reservations or participant entitlements.
- A `STALE` or `CORRECTED` event can never be promoted to an accepted
  repayment solely because it appears in this history.
- Pagination is an observed read across HTTP transactions, not an
  immutable multi-page snapshot or a financial sequencing guarantee.
- BL-020/021/023/026 prerequisites and BL-027/028/029 remain unimplemented
  pending approved allocation, expiry, provider/payment and captured
  product policy; no inferred constants, reserve values or risk PASS.
- Merge, Stage, QA, Release, Production and Figma remain unauthorized.

`Code = COMPLETE`

`Technical Code Review = COMPLETE`

`Merge / Stage / QA / Release / Production = NOT AUTHORIZED`
