# Sprint 48 — Supporting Institution Workspace

- **Status:** Implementation slice, stacked after Sprint 47.
- **Backlog:** BL-061 supporting institution workspace foundation.
- **Code authorization:** Decision 0066.

## Goal

Give supporting institution operators a separate panel to view only the beneficiaries attached to programs explicitly authorized for their identity.

## Scope

- Add a distinct SUPPORT_INSTITUTION_OPERATOR role scoped to a single program.
- Allow global governance to request and approve program-scoped access using maker-checker control, and revoke requested or active grants.
- List only active programs assigned to the caller.
- Read beneficiaries through participation episodes for an exact authorized program.
- Audit grant changes, workspace reads, and denied access.

## Acceptance Criteria

1. A global grant cannot substitute for the exact program-scoped operator grant.
2. Only active human identities and active programs linked to a legal entity can receive operator access.
3. The requester cannot approve their own grant.
4. Program lists and beneficiary reads disclose only authorized program scope.
5. Beneficiary rows contain no national ID or financial case data.
6. No profile, enrollment, consent, capital, eligibility, guarantee, pension, post-exit support, or payment state is mutated.

## Gates

- Exact-head CI and technical review are required.
- No merge, Stage, release, or production operation is authorized.
