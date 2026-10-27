# Decision 0076 — Automatic Individual Profile Provisioning

- **Status:** Code authorized to complete the automatic profile behavior already accepted in Decision 0065.
- **Authority:** Decision 0065 requires profile creation for an authenticated individual with a verified OIDC national-ID claim.
- **Scope:** Sprint 58 provisions the matching participant profile during authenticated request resolution.

## Decision

When an active PARTICIPANT identity authenticates with a verified, non-empty national-ID claim, Badban resolves the exact matching participant record. If none exists, it creates one once and records an audit event. Concurrent requests reuse the record created by the competing request. Existing participant records introduced by institutions are reused by exact identifier.

## Boundaries

- The claim is trusted only after the configured OIDC verifier validates the token.
- The identifier is used for matching and is not returned by applicant APIs.
- Profile creation does not enroll the person in a program, assign funds, approve eligibility, or create a guarantee, entitlement, or payment.
- Other identity types and identities without the verified claim do not cause participant-profile creation.
- No merge, Stage, QA release gate, Release, or Production operation is authorized.
