# Decision 0064 — Sprint 46 Role-Scoped Admin Operations

- **Status:** Code authorized for the bounded service operations slice.
- **Authority:** Owner direction to complete the distinct Badban admin experience.
- **Backlog:** BL-058.

## Decision

Expose read-only operational queues for guarantee, monthly pension, and post-exit support, each requiring a role grant scoped to that service. Service scopes use stable UUIDv5 identifiers derived from the service code. The existing `role_grants` table stores the service scope and remains the authorization source.

Use the existing logical staff roles. Guarantee operations allow OPERATIONS, RISK, LEGAL_COMPLIANCE, GOVERNANCE_APPROVER, and AUDITOR. Monthly pension and post-exit operations allow OPERATIONS, FINANCE_RECONCILIATION, GOVERNANCE_APPROVER, and AUDITOR. A role can be requested by a global governance approver, becomes active only after a different global governance approver approves it, and can be revoked with an audited reason.

## Boundaries

- Operational queues are read-only. No ledger editing, payment instructions, policy activation, guarantee issuance, or entitlement decision is added.
- Queue reads are audited. Existing source evidence, calculation references, service status, and lender-record state remain separate fields.
- Role grants apply only to human staff identities and deny access without a service-scoped active grant.
- No merge, Stage, release, or production operation is authorized.
