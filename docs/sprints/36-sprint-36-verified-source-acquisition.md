# Sprint 36 — Verified Source Acquisition Boundary

- **Status:** Code authorized; Draft PR pending implementation/review
- **Date:** 2026-10-25
- **Decision:** [0054 — Verified Source Acquisition Boundary](../decisions/0054-sprint-36-verified-source-acquisition-code-authorization.md)
- **Backlog:** BL-042 technical source-boundary work only

## Objective

Provide one read-only application service that resolves an explicitly
registered source, confirms its capability has not changed since registration,
acquires a snapshot, and verifies the snapshot against the exact target, scope,
and registered versions before exposing it to any comparison or persistence
caller.

## In scope

- Pin immutable `SourceCapability` metadata at registry registration.
- Fail closed if a port later advertises different capability metadata.
- Acquire and verify canonical snapshots through a single service boundary.
- Classify unavailable, timeout, transport, and source-contract failures.
- Add unit coverage for successful verification and each failure class.

## Explicitly out of scope

- Source provider implementations or credentials.
- Run/case/observation persistence or API endpoints.
- Reconciliation comparisons, matching, freshness, tolerance, and materiality.
- Financial, legal, risk, reservation, guarantee, or journal state changes.
- Stage, QA completion, Release, Production, and real-money behavior.

## Acceptance

- No unregistered or changed-capability source yields a snapshot.
- No mismatched or tampered snapshot is returned.
- Error responses contain stable codes and do not expose provider exception
  details.
- The existing lender reconciliation path and persistence schema are unchanged.
- Keep the PR Draft/Open/unmerged until exact-SHA CI and code review complete.
