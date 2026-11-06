# Sprint 62 — Institution and Lender Complete Read Pagination

**Branch:** feat/figma-web-foundation-live-read-models, stacked onto PR #70. **Base HEAD:** f71c2bbdc51492c53590e7b725bc2b8348c49d9b.
**Scope:** backend-contract-first UI reading only. Keep PR Draft/Open, no merge, Stage, QA release, or Production.

## Implemented
- Four independently paged workspaces using existing backend GET contracts:
  - /api/v1/support-institution/programs?limit=25&offset=N
  - /api/v1/support-institution/programs/{program_id}/beneficiaries?limit=25&offset=N
  - /api/v1/lender/providers?limit=25&offset=N
  - /api/v1/lender/providers/{provider_id}/guarantees?limit=25&offset=N
- Expose next/previous page and explicit refresh without inventing total counts or monetary summaries.
- Parent scope changes, pagination and refresh immediately hide prior financial/guarantee detail and suppress previous response state.
- Validate exact response limit/offset and parent UUID, bound row count, unique IDs and existing deep nested guarantee/person checks before display.
- Reuse current read-only individual financial detail and lender guarantee detail components; no new financial endpoints or fake data.
- Preserve Figma RTL navy/gold panels, selectable cards and program/guarantee rows.

## Security and product boundaries
- A scope selector does not grant permission: each GET must pass existing backend role/grant authorization.
- Organization-owned money remains organization-owned; beneficiary is an eligible user of returns only under the relevant rules.
- No bulk import, enrollment, deposit, withdrawal, payment, guarantee issuance, decision, or settlement action is enabled.
- Financial amounts and program/lender counts are taken only from current server responses, never from Figma mock data.
- When a page is exactly full, "next" can lead to an empty page because the backend has no total-count contract.

## Acceptance
- Vitest covers precise paths, malicious IDs, malformed pages, duplicate IDs, scope binding, decimal integrity, and pagination boundaries.
- Strict TypeScript/Vite Web Candidate CI and full GitHub CI are required before the technical review can be marked COMMENTED.
- Browser-level identity flow and screenshot regression against approved Figma frames remain outstanding.


## Validation record — 2026-11-05

- Code commit: \`c10e2dc3d089c576d478afa454d9b7e1a52d196e\`.
- Web Candidate CI #42051367164: SUCCESS (26 Vitest tests, including 7 pagination tests; strict TypeScript and Vite build).
- Full CI #42051367188: SUCCESS (secret scan, format, lint, type-check, Alembic migrations/drift, backend tests, dependency audit, container build).
- Technical Code Review: COMMENTED on PR #70, review id \`5787162797\`. This is not human approval or a release authorization.
- Main is unchanged; PR remains Draft/Open/unmerged. No Stage, QA Gate, Release Approval or Production deployment.

## Deferred
- OIDC real-browser end-to-end and screenshot comparison with approved Figma viewports.
- On a failed page load, previous navigation currently requires refreshing the page first.
- Bulk import, capital funding, withdrawal, payment/settlement and guarantee mutation remain out of scope pending approved backend contracts.
