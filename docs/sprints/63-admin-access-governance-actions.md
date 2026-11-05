# Sprint 63 — Supporting Institution and Lender Access Governance Actions

**Base:** PR #70 Draft/Open at \`25cfc8c213970d297264ed4f19d303d8dcdfc487\`.
**Scope:** UI integration of already implemented, backend-authorized grant request / approve / revoke commands. No new business state machine or permission semantics.

## Approved existing contracts
- Decision 0066: supporting-institution access is a program-scoped human grant; request -> different governance approver -> active; exact-scope access and revocation.
- Decision 0067: lender access is a provider-scoped human grant; global governance requests/approves with maker-checker and may revoke.
- Decision 0068: AdminWorkspaceIndex is descriptive; UI capability visibility does not grant permission.
- Existing endpoints:
  - GET/POST /api/v1/admin/support-institution/grants
  - POST /api/v1/admin/support-institution/grants/{grant_id}/approve
  - POST /api/v1/admin/support-institution/grants/{grant_id}/revoke
  - GET/POST /api/v1/admin/lender-access/grants
  - POST /api/v1/admin/lender-access/grants/{grant_id}/approve
  - POST /api/v1/admin/lender-access/grants/{grant_id}/revoke
  - GET /api/v1/me (identity id used only for maker/checker UX).

## Implemented
- New grant request form for a human identity and exact Program or Provider UUID.
- Time-window conversion from browser local datetime to timezone-aware UTC ISO timestamp; optional end time remains null.
- Reason reference required for requests; reason required for revocation.
- Requested grant can be approved only by another governance identity; same requester is disabled in UI and backend remains authoritative.
- Requested and Active grants can be revoked with a reason; successful commands refresh the exact status-filtered queue.
- Visibility requires a global-scope governance workspace and its exact MANAGE_* capability. Every endpoint still independently authorizes.
- Benefit-lineage review remains read-only; no unrelated decision workflow was changed.

## Explicit gaps retained
- There is no current API to search/list human identities or legal entities for the request form; identifiers must be obtained from an independently authorized source. No PII directory or invented organization records are shown.
- No generic organization creation or program CRUD, participant directory, participant enrollment, bulk import, deposit, withdrawal, payment, settlement or guarantee issuance is added.
- Service-role grant commands exist, but a corresponding list/read queue is not yet available to the UI; this slice does not invent one.

## Validation
- Unit tests cover exact routes/payloads, UUID confinement, aware timestamps, time-window ordering and mandatory revocation reason.
- Full web candidate and repository CI must pass on the exact head.
- Real OIDC browser tests and screenshot comparison remain separate follow-up work.
