# Decision 0059 — Sprint 41 Configurable Three-Service Catalogue

- **Status:** Code authorized for the bounded Sprint 41 scope.
- **Authority:** Project owner instruction to align Badban to the supplied proposal and continue the remaining work.
- **Source:** `docs/business/03-original-proposal-product-alignment.md` and `docs/technical/16-three-service-domain-boundaries.md` (stacked PRs #50 and #51).
- **Backlog:** First implementation slice of BL-054.
- **Sprint plan:** `docs/sprints/41-sprint-41-configurable-three-service-catalogue.md`.

## Decision

Implement a versioned, configurable catalogue for the three Badban service types: `LOAN_GUARANTEE`, `MONTHLY_PENSION`, and `POST_EXIT_SUPPORT`. Keep the existing provider-specific `CreditProductVersion` and guarantee lifecycle separate. Catalogue entries start in `DRAFT`; no service is activated by default.

Policy configuration must fail closed when required information is missing or invalid. Any post-exit support window must be bounded to at most 36 months. Eligibility and benefit formulas remain policy-provided; this sprint must not invent monetary values, eligibility thresholds, or payout timing.

## Controls

- Applicant read models expose only explicitly active, effective catalogue versions.
- Admin writes are authenticated, permission-scoped, audited, and idempotent where commands are retried.
- No lender, payment, pricing, custody, or other external source is activated by this decision.
- Existing lender-of-record, principal-preservation, and guarantee controls remain unchanged.
- Code review and exact-head CI are required before any later merge consideration.
- This decision does not authorize Stage, release, or production operations.
