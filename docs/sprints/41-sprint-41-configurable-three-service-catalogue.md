# Sprint 41 — Configurable Three-Service Catalogue

- **Status:** Planned implementation slice; code remains on a separate Draft PR.
- **Business basis:** Original-proposal alignment addendum and three-service domain-boundary design.
- **Backlog:** BL-054 (first implementation slice).
- **Code authorization:** Decision 0059.

## Sprint Goal

Represent Badban's three distinct services as versioned catalogue entries with fail-closed policy configuration, without claiming any service or external provider is operationally active.

## In Scope

- Add a service catalogue version aggregate with stable codes for loan guarantee, monthly pension, and post-exit support.
- Persist policy configuration and effective windows as immutable versioned records.
- Add authorized admin commands to create draft catalogue versions and read-model queries for admin and applicant surfaces.
- Expose only explicitly approved/active catalogue versions to applicants; new entries default to DRAFT.
- Validate service-specific policy shape and enforce the maximum 36-month window for post-exit support when supplied.
- Add migration, audit evidence, and deterministic automated coverage.

## Out of Scope

- Eligibility, contribution, benefit amount, rounding, investment, or payout formulas not supplied by approved business policy.
- Monthly or post-exit entitlement generation/payment.
- Activating lenders, payment providers, price sources, or live investment observations.
- UI implementation, Stage, QA sign-off, release, or production operation.

## Acceptance Criteria

1. All three service codes can be represented independently; the guarantee product registry remains provider-specific.
2. Missing or malformed policy configuration is rejected and cannot create an active service.
3. Every created version captures its actor, policy reference, effective window, and audit record.
4. An applicant query cannot see DRAFT, suspended, retired, or not-yet-effective service versions.
5. Post-exit support cannot be configured for a duration over 36 months.
6. Migration downgrade removes only the new catalogue schema and does not alter existing guarantee/product data.
7. Automated tests cover allowed service types, invalid policy, lifecycle visibility, authorization, effective windows, and the 36-month bound.

## Dependencies and Gates

- Stacked on PR #51 (technical boundaries and backlog extension), itself stacked on PR #50 (business alignment).
- External source registry remains configurable but has no verified live provider in this slice.
- All new service versions remain DRAFT until explicit approval commands and evidence are implemented in a later slice.
- No Stage, release, merge, or production action is authorized by this plan.
