# Sprint 47 — Universal Individual Profile

- **Status:** Implementation slice, stacked after Sprint 46.
- **Backlog:** BL-060 profile foundation.
- **Code authorization:** Decision 0065.

## Goal

Allow an ordinary individual to enter Badban through a verified national ID while preserving existing institution-introduced participant records.

## Scope

- Resolve the authenticated participant to the unique record matching the verified OIDC national ID.
- Create the individual profile automatically when that record does not exist.
- Make creation safe under concurrent requests and audit it.
- Keep program enrollment, capital assignment, and service eligibility separate from profile creation.

## Acceptance Criteria

1. Only a `PARTICIPANT` identity with a non-empty verified national ID can resolve or create the profile.
2. Existing records are reused; concurrent first requests do not create duplicate profiles.
3. The response contains no national ID.
4. Profile creation does not create a participation episode, capital position, entitlement, or guarantee.
5. Supporting institution access remains program-scoped and is delivered as a separate workspace slice.

## Gates

- Exact-head CI and technical review are required.
- No merge, Stage, release, or production operation is authorized.
