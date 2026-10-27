# Sprint 58 — Automatic Individual Profile Provisioning

## Goal

Make the accepted individual-profile behavior automatic at authentication, so applicant read and request flows do not require a separate profile-creation call.

## Deliverables

- Resolve the participant by the verified OIDC national-ID claim during principal resolution.
- Create the exact-match profile on first authenticated use when absent.
- Reuse an existing institution-introduced participant profile.
- Keep creation race-safe and audited.
- Preserve least privilege: profile creation does not enroll or confer service eligibility.

## Boundaries

- No caller-supplied participant ID or unverified claim is used.
- No program enrollment, funds, entitlement, guarantee, or payment is created.
- The national ID is never included in the applicant response or generic audit payload.
- No merge, Stage, QA release gate, Release, or Production operation is authorized.
