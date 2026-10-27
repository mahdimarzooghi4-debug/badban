# Decision 0068 — Role-Derived Admin Workspace Index

- **Status:** Code authorized for a read-only role-derived admin navigation index.
- **Authority:** Owner direction that administrators have different access levels and the admin panel must reflect those levels.
- **Scope:** Sprint 50 workspace discovery endpoint.

## Decision

The admin client may request a workspace index derived only from the caller's currently active role grants. The index lists service-operation workspaces only for exact service-scoped role grants allowed by that service's role matrix. Global governance access exposes grant-management capabilities for service, supporting-institution, and lender roles.

The index is descriptive navigation data. Each underlying API continues to enforce its own authorization independently.

## Boundaries

- No workspace is exposed based on an inactive, future, expired, or unrelated scope grant.
- The index does not grant or change permissions and does not replace authorization on protected routes.
- It does not return participant, lender, or financial records.
- No merge, Stage, release, or production operation is authorized.
