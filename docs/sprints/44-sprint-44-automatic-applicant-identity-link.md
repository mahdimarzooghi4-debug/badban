# Sprint 44 — Automatic Applicant Identity Link

- **Status:** Implementation slice, stacked after Sprint 43.
- **Backlog:** BL-057 prerequisite.
- **Code authorization:** Decision 0062.

## Goal

Automatically resolve an authenticated participant account to exactly one Badban participant record using a trusted, signed OIDC claim.

## Scope

- Add a configurable OIDC national-ID claim name with default `national_id`.
- Carry the verified claim into the authenticated principal.
- Add a self-scoped read endpoint that resolves only an exact `participants.external_reference` match and never returns the national ID.
- Fail closed for non-participant identities, missing claims, and unmatched participant records.
- Document the required identity-provider claim contract.

## Acceptance Criteria

1. The participant reference comes only from a token already verified for signature, issuer, audience, and expiry.
2. The endpoint does not accept a participant ID or reference from query/body parameters.
3. A unique exact external-reference match is required; no fuzzy or personal-data matching is performed.
4. Only the linked participant's basic identity reference and lifecycle status are returned.
5. Missing/unmatched links do not reveal whether another participant record exists.

## Gates

- Exact-head CI and technical review are required.
- The identity-provider claim mapping must be configured before applicant accounts can resolve.
- This sprint does not complete BL-057 financial summaries.
- No merge, Stage, release, or production operation is authorized.
