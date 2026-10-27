# Sprint 49 — Lender Workspace

- **Status:** Implementation slice, stacked after Sprint 48.
- **Backlog:** BL-059 lender portal foundation.
- **Code authorization:** Decision 0067.

## Goal

Provide a separate lender panel showing only that lender provider's guarantee cases and recorded loan facts.

## Scope

- Add a distinct LENDER_OPERATOR role scoped to one credit provider.
- Allow global governance to request, review, approve with maker-checker control, and revoke lender access.
- List only active providers granted to the caller.
- Provide a read-only provider-scoped guarantee worklist with linked external-loan mirror fields when available.
- Keep guarantee exposure distinct from lender-reported loan principal and include currencies.
- Audit grant actions and lender workspace reads.

## Acceptance Criteria

1. Access is restricted to an active human identity with an active exact-provider grant.
2. A global role grant cannot substitute for a provider-scoped lender role grant.
3. Grant approval requires a different governance identity than the requester.
4. Every guarantee row is filtered by its provider ID and does not include participant identity fields.
5. Missing external-loan mirror data remains null; no loan state or payment is inferred.
6. No guarantee, loan, payment, reconciliation, or participant state is mutated.

## Gates

- Exact-head CI and technical review are required.
- No merge, Stage, release, or production operation is authorized.
