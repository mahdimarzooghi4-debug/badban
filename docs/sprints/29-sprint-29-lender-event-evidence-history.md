# Sprint 29 — Provider-Scoped Lender Event Evidence History

- **Date:** 2026-10-09
- **Status:** Code / tests / CI in progress
- **Dependency:** Draft PR #31 (Sprint 28) with full CI #439 success
- **Scope:** Backend-only, Technical 07 §21 and Technical 08 event lineage
- **Decision:** technical event-evidence query authorization only; no new business policy

## Goal

Make the already-persisted authenticated, normalized lender event history
independently inspectable to scoped staff, so subsequent repayment and
delinquency workflows can audit authoritative versus stale or
history-only provider observations. This is **not** BL-027 repayment
application or BL-028 guarantee exposure reduction.

## Contract

- `GET /api/v1/external-loans/{loan_id}/events`: Provider-scoped
  OPERATIONS / FINANCE_RECONCILIATION / AUDITOR authorized staff.
  Return immutable recorded event fields, actual `processed_status`,
  evidence references, source payload digest and source contract versions.
  This does not return raw provider payload or any ability to mutate.
- Stable deterministic keyset by
  `(provider_event_at, event.id)`; the `after` UUID must
  refer to an event on the **same loan**, otherwise error.
  Max page length 100, explicit `next_cursor`.
- `GET /api/v1/external-loans/{loan_id}/events/{event_id}`:
  exact event from the same loan under same provider-scoped grant.
  Cross-loan detail returns 404, foreign cursor returns 422.
- All money/quantity values from NUMERIC are represented as **decimal
  strings**, including signed observed principal deltas.
- Raw statuses `APPLIED`, `STALE`, `HISTORY_ONLY`, `CORRECTED`
  are displayed, not treated as business approval or a source for
  automatic financial transactions.
- Test consent/authorization, empty history, role revocation,
  multiple events / cursor paging, source/version precision, cross-loan
  denial, and no implicit guarantee/journal transitions.

## Non-goals

- No lender integration credentials or provider-specific adapters.
- No repayment application to GuaranteeCase; no exposure decrease,
  release, reserve, credit, payout, Journal or reconciliation changes.
- No Stage/QA/Release/Production, Merge, Figma, or real-money operations.
- BL-020/026/027/028 remain blocked on authoritative, approved
  reservation/activation and product-specific financial contracts.
