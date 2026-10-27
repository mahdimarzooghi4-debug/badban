# Sprint 46 — Role-Scoped Admin Service Operations

- **Status:** Implementation slice, stacked after Sprint 45.
- **Backlog:** BL-058.
- **Code authorization:** Decision 0064.

## Goal

Provide separate, read-only admin work queues for the three services with explicit role and service scope.

## Scope

- Reuse the existing role-grant store with a stable service scope identifier.
- Add maker-checker grant request/approval and audited revocation for human identities.
- Apply a service-specific allowlist of existing staff roles.
- Add read-only queues for guarantee cases, monthly pension entitlements, and post-exit cases/entitlements.
- Audit successful work-queue reads; do not expose ledger mutation or payment actions.

## Acceptance Criteria

1. No admin queue is available without an active grant for the exact service scope and an allowed role.
2. Global roles do not implicitly grant service access.
3. Service role requests require a separate global governance checker before activation.
4. Role grants can be revoked and all grant lifecycle actions are audited.
5. Queue fields keep source evidence, calculation references, operational state, and lender-record presence distinct.
6. Operations views do not directly mutate journals, balances, entitlements, or guarantee state.

## Gates

- Exact-head CI and technical review are required.
- No merge, Stage, release, or production operation is authorized.
