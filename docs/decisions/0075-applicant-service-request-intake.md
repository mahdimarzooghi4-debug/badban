# Decision 0075 — Applicant Service Request Intake

- **Status:** Code authorized for initial service request intake by an authenticated individual.
- **Authority:** Owner confirmed that an ordinary individual may submit a service request after their individual profile exists.
- **Scope:** Sprint 57 records initial requests for the three Badban services and exposes a service-scoped administrative queue.

## Decision

An authenticated individual with a verified OIDC national-ID claim may submit an initial request for loan guarantee, monthly pension, or post-exit support after Badban resolves their individual profile. The API derives the participant from the verified claim; callers cannot submit a participant ID.

Requests enter the single state RECEIVED. They are visible to the same applicant and to staff whose active service-scoped role grants access to the relevant service queue. Requests are idempotent and audited.

## Boundaries

- RECEIVED means only that Badban recorded the request; it is not eligibility approval or acceptance into a program.
- Submission does not create a guarantee case, participation episode, entitlement, fund allocation, payment, or financial obligation.
- No eligibility criteria, amounts, required documents, review statuses, rejection rules, or contact channels are invented.
- The queue exposes participant and request IDs but does not return national IDs or other profile identifiers.
- No merge, Stage, QA release gate, Release, or Production operation is authorized.
