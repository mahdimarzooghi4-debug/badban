# Decision 0066 — Supporting Institution Workspace

- **Status:** Code authorized for a bounded, read-only, program-scoped workspace.
- **Authority:** Owner direction that ordinary individuals use Badban directly while a supporting institution panel serves only its referred beneficiaries.
- **Scope:** Sprint 48 workspace foundation.

## Decision

A supporting institution operator may read the programs explicitly assigned to their identity through an active PROGRAM-scoped role grant. Within an assigned program, the operator may read participation episode identifiers, participation status, consent state, and participation dates for linked participants.

Access is issued by global governance as a requested role grant and activated only by a different governance approver. Grants require an active program linked to a legal entity and an active human identity. Governance can revoke active or requested grants. Access checks are exact-scope and auditable.

## Boundaries

- The workspace does not return national IDs, personal contact details, capital balances, guarantees, pension amounts, or post-exit payment details.
- The workspace is read-only: it does not enroll participants, change consent, assign capital, establish eligibility, or create services.
- Individual profile creation remains separate from program participation.
- No merge, Stage, release, or production operation is authorized.
