# Decision 0067 — Lender Workspace

- **Status:** Code authorized for a bounded, provider-scoped, read-only lender workspace.
- **Authority:** The Badban service design assigns lenders their own surface for the guarantees and loan facts associated with their provider.
- **Scope:** Sprint 49 lender workspace foundation.

## Decision

A lender operator may access only active credit providers explicitly granted to their human identity through an active PROVIDER-scoped role grant. The provider workspace lists guarantees issued for that provider and any linked external-loan mirror facts already recorded by Badban.

Global governance requests and approves the operator grants using maker-checker control and may revoke them. Provider scope is exact; a global grant does not substitute for the lender operator grant.

## Boundaries

- The workspace returns guarantee and lender-reported loan lifecycle facts only; it does not return participant identity, national ID, contact data, or supporting-institution case details.
- Reads distinguish guarantee exposure from provider-reported outstanding loan principal and keep each currency explicit.
- The workspace does not issue or release guarantees, disburse loans, change loan status, or assert that payment or reconciliation occurred.
- External loan facts appear only when already recorded through existing provider integrations.
- No merge, Stage, release, or production operation is authorized.
