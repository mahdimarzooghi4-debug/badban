# Decision 0072 — Admin Benefit Lineage Review Workspace

- **Status:** Code authorized for role-derived discovery of the legacy benefit lineage review queue.
- **Authority:** Decision 0071 established a governance-only maker-checker queue; Sprint 50 established role-derived admin workspace discovery.
- **Scope:** Sprint 54 adds a dedicated workspace entry to the admin workspace index.

## Decision

The admin workspace index returns an `ADMIN_BENEFIT_LINEAGE_REVIEW` entry only when the caller has an active global `ROLE_GOVERNANCE_APPROVER` grant. The entry advertises queue read, request, approval, and rejection capabilities and points the admin client to the existing `/api/v1/admin/benefit-lineage/reviews` API.

The workspace entry is discoverability metadata. It does not grant access; the queue endpoints independently check the same global governance role, and maker-checker rules remain in force.

## Boundaries

- Service-scoped grants and inactive or expired global grants do not expose this workspace.
- No new data, workflow, or authorization is introduced.
- Queue responses continue to omit benefit amounts and national identifiers.
- No merge, Stage, release, or production operation is authorized.
