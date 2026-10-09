# Sprint 31 — Governed Audit Trail Query Foundation

- **Date:** 2026-10-09
- **Scope:** Backend-only BL-044 / accepted Technical 07 §33, Technical 11 §14
- **Base:** Sprint 30 PR #33, exact-head CI #448 SUCCESS
- **Status:** Draft code; CI and independent Code Review pending

## Contract

Expose the existing immutable `AuditEvent` persistence to authorized
AUDITOR identities without a mutation endpoint:

- `GET /api/v1/audit/events`: bounded read-only query by optional exact
  aggregate type/ID, action and correlation ID.
- `GET /api/v1/audit/aggregates/{aggregate_type}/{aggregate_id}`:
  exact aggregate audit lineage with the same authorization and ordering.
- `program_id` requests require active AUDITOR grant for that Program or
  a GLOBAL AUDITOR grant. Program-scoped requests return only records
  explicitly tagged at write time with the matching Program scope.
  Missing/legacy/ambiguous scope stays invisible to program-scoped users.
- Omitting `program_id` requires an actual GLOBAL AUDITOR grant. Neither
  STAFF operations role, technical service identity nor a revoked grant
  grants audit access.
- Cursor is an existing event ID from the **same filtered authorized
  stream**, ordered by `(occurred_at, id)`; invalid/mismatched cursors
  fail with `422 AUDIT_CURSOR_INVALID`. Page size 1–100.
- Read model includes actor, reason, action, policy/evidence reference,
  correlation/causation, aggregate and time. It deliberately **excludes**
  arbitrary `previous_state`, `new_state` and `scope` JSON, and never
  returns raw evidence, provider payload or credentials.
- Read-only queries do not change journal, guarantee, reserve, risk,
  exposure or any financial/operational source.

## Acceptance tests

OpenAPI read-only and minimized schema; live PostgreSQL pagination,
exact-scope/aggregate/correlation filtering; cross-program/cross-filter
cursor rejection; no state-payload leakage; missing or revoked Auditor
grant, non-human identity and insufficient role denied; GLOBAL Auditor
can inspect otherwise unscoped legacy audit metadata. All tests must
run in existing GitHub full CI.

## Boundaries

This is a metadata audit explorer and does not authorize BL-020
reservation, provider settlement, financial adjustments or exception
overrides. Scope tags remain authoritative; neither audit query nor
its caller may infer program ownership for missing scope records.
No Stage/QA/Release/Production/Figma or PR merge.
