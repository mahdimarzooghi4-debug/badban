# Sprint 50 — Role-Derived Admin Workspace Index

- **Status:** Implementation slice, stacked after Sprint 49.
- **Backlog:** BL-062 admin workspace capability discovery.
- **Code authorization:** Decision 0068.

## Goal

Let the admin client display only the service-operation and grant-governance sections available to the signed-in administrator.

## Scope

- Read the caller's active, effective role grants.
- List only service workspaces supported by the existing service role matrix and exact service scope.
- Advertise global governance grant-management sections only for an active global governance grant.
- Audit the capability-index read.
- Keep authorization checks on each destination API unchanged.

## Acceptance Criteria

1. Future, expired, revoked, and unrelated scope grants do not appear.
2. A global role does not create service-operation entries.
3. Each service entry contains only roles allowed by that service's matrix.
4. Governance capabilities appear only under exact GLOBAL scope.
5. The response contains no domain records or personal/financial data.
6. The index does not create, alter, or substitute for any grant.

## Gates

- Exact-head CI and technical review are required.
- No merge, Stage, release, or production operation is authorized.
