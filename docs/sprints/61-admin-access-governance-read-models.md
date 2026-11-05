# Sprint 61 — Admin Access Governance Read Models

**Base:** PR #70 current head \`a991d498f27b6fbcff943face0ad20d878149a36\`.
**Status:** Draft code candidate. No merge, Stage, QA, Release or Production.

## Figma alignment
Admin dashboard node \`271:3\` includes the "دسترسی و راهبری" workspace. This slice adds read-only governance queues within the same navy/gold RTL admin visual system.

## Existing backend contracts
- GET \`/api/v1/admin/support-institution/grants?status=REQUESTED|ACTIVE|REVOKED&limit=25&offset=N\`
- GET \`/api/v1/admin/lender-access/grants?status=REQUESTED|ACTIVE|REVOKED&limit=25&offset=N\`
- GET \`/api/v1/admin/benefit-lineage/reviews?status=REQUESTED|APPROVED|REJECTED&limit=25&offset=N\`

Visibility is derived from \`ADMIN_ACCESS_GOVERNANCE\` and \`ADMIN_BENEFIT_LINEAGE_REVIEW\` workspace entries and their explicit capabilities. Every backend endpoint independently enforces the global governance role.

## Boundaries
- Read-only queues only. No grant request, approval, revocation, or lineage decision commands are exposed.
- IDs are displayed in shortened form; evidence and reason references are not treated as approval.
- No permission is created by showing a workspace entry.
- Exact status, role, scope, page, and timestamp response validation fails closed.
- No synthetic totals or inferred decision states.


## Acceptance and review record — 2026-11-05

- Implementation commit: \`7eecfe2780da459a6bd9353aa56ce8a7a5bfa8ef\`.
- Web Candidate CI #42049360165: SUCCESS — Vitest, strict TypeScript and Vite production build.
- Full CI #42049360194: SUCCESS — secret scan, format, lint, type check, migrations, migration drift, backend tests, dependency audit and container build.
- Technical review: COMMENTED on PR #70 (review id \`5786957952\`); no merge/release approval.
- PR #70 remains Draft/Open; main unchanged. No Stage, QA admission, release approval, merge or Production deployment.
- Outstanding: real OIDC/browser E2E and screenshot comparison against approved Figma viewports.
