# Sprint 64 — Role-Scoped Administrative Reference Directories

- **Status:** Code in progress; stacked on Draft PR #70.
- **Backlog:** BL-054.
- **Code authorization:** Decision 0077.
- **Base:** 4252c667682903ee02bdb56db4a7491b647f74f6.

## Goal

Complete the central admin's reference directory layer using existing database facts and already-established global roles, without exposing a global beneficiary directory or changing business state.

## Scope

### 1. Human identity directory
- GET /api/v1/admin/directory/identities
- Global ROLE_GOVERNANCE_APPROVER only.
- Human identity types only: STAFF, GOVERNANCE, AUDITOR.
- Returns identity UUID, type, status, creation time.
- Never returns OIDC subject, national ID, contact details, participant identities, or service identities.

### 2. Legal entity directory
- GET /api/v1/admin/directory/legal-entities
- Global ROLE_GOVERNANCE_APPROVER, ROLE_LEGAL_COMPLIANCE, or ROLE_AUDITOR.
- Returns UUID, legal name, entity type, status, version, creation time.
- Never returns registration identifier, legal-authorization identifiers/evidence, contacts, or financial data.

### 3. Program directory
- GET /api/v1/admin/directory/programs
- Global ROLE_GOVERNANCE_APPROVER, ROLE_AUDITOR, or ROLE_OPERATIONS.
- Returns UUID, code, name, status, linked legal-entity UUID, version, creation time.
- No beneficiaries, counts, eligibility, balances, or financial data.

### 4. Role-derived workspace discovery
- Extend GET /api/v1/admin/workspace with separate global entries for the three directory capabilities.
- Only active, effective global grants appear.
- Directory APIs independently enforce authorization and append read audit.

### 5. Web
- Add read-only, paginated directory panels for the three API resources.
- Validate response shape, pagination, UUIDs, timestamps, and privacy allowlists.
- Keep beneficiary data in the existing exact-program and exact-service workspaces only.

## Explicit non-goals

- No global participant/beneficiary directory.
- No identity or legal-entity search integration; the current Identity model has no display name or contact fields.
- No CRUD, legal verification, provider activation, role mutation, program enrollment, eligibility, financial commands, or payments.
- No migration is expected; this slice reads existing tables only.

## Acceptance

- Unauthorized, service-scoped-only, inactive, future, expired, or unrelated roles cannot read directories.
- Response schemas exclude external subjects, registration identifiers, national IDs, and beneficiary data.
- Every successful directory read is audited.
- Workspace discovery is derived from current active global grants and does not replace endpoint authorization.
- Backend integration tests cover role/scope denial, pagination, field allowlists, and audit.
- Web tests cover endpoint paths, page identity, UUID/timestamp validation, and forbidden-field rejection.
- Full CI and Web Candidate CI must be green on exact HEAD; technical review is COMMENTED only.

## Gates

PR remains Draft/Open. No merge, Stage, QA gate, Release Approval, Production, or real-money operation is authorized.
