# Sprint 60 — Operational Figma Details and Scoped Read Workspaces

**Base:** Draft PR #70 at 5bf7db507bc29382242443b5f6b0dc7c58949e1b.
**Status:** code candidate; keep Draft/Open. No merge, Stage, QA, Release or Production.

## Delivered
- Supporting institution: program/participant/episode-scoped financial detail from the existing backend route. Includes asset ownership source, historical valuation observations, guarantees, monthly entitlements, post-exit support and program-level return allocation.
- Lender: selected guarantee detail remains inside the current provider's authorized list.
- Admin: service request intake queue is derived only from active SERVICE-scoped workspace entries carrying READ_APPLICANT_SERVICE_REQUESTS, and calls the backend-authorized service queue endpoint.
- Admin queue uses 25-row offset pagination, validates exact service, offset, limit, timestamp and RECEIVED-only state.
- Scope-aware async read state suppresses data from the prior user/program/provider/service before the next effect completes.
- All displayed financial values are validated decimal strings; missing values remain unavailable and never become zero.

## Backend contracts
- GET /api/v1/support-institution/programs/{program_id}/beneficiaries/{participant_id}/episodes/{episode_id}/financial-case
- GET /api/v1/lender/providers/{provider_id}/guarantees
- GET /api/v1/admin/workspace
- GET /api/v1/admin/service-operations/{service_code}/applicant-requests?limit=25&offset=N

Every endpoint enforces authorization independently. The UI does not confer or widen grants.

## Non-capabilities
No deposit, withdrawal, allocation, enrolment, guarantee issuance, payment, settlement, approval, rejection, or applicant eligibility. RECEIVED is request intake only. Program return totals are explicitly labeled at program/person scope, not as an episode balance.

## Validation
- Strict schema validation of nested asset/valuation, guarantee, loan, pension, post-exit, and program-return facts.
- Vitest covers path confinement, exact scope, malformed financial facts, permission-derived admin navigation, and intake pagination/state.
- Full Vite build and GitHub CI are the acceptance gate for this code candidate.
