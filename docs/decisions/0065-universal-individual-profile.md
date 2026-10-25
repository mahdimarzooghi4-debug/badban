# Decision 0065 — Universal Individual Profile

- **Status:** Code authorized for a bounded individual-profile slice.
- **Authority:** Owner direction that Badban serves ordinary individuals and also supports beneficiaries introduced by supporting institutions.
- **Scope:** Sprint 47 profile foundation.

## Decision

Every authenticated individual with a verified OIDC `national_id` claim can resolve a Badban individual profile. If no participant record exists for that exact verified identifier, Badban creates the profile once and audits the creation. Existing institution-introduced participant records are reused by the same unique identifier.

Creating an individual profile does not enroll the person in a supporting program, assign capital, or establish eligibility for a service. Those states require their own approved workflow and evidence. Supporting institutions continue to manage only people linked to their authorized program scope.

## Boundaries

- The identity provider must verify the national ID before issuing the configured claim.
- The identifier is not returned in applicant responses.
- This slice does not activate an investment, entitlement, guarantee, or payment.
- No merge, Stage, release, or production operation is authorized.
