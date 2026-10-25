# Decision 0062 — Automatic Applicant Identity Link

- **Status:** Code authorized for the bounded Sprint 44 identity-link slice.
- **Authority:** Owner direction that applicant identity and participant records must connect automatically.
- **Backlog:** BL-057 prerequisite.

## Decision

Resolve the authenticated participant to a Badban participant record using a configurable national-ID claim from the already verified OIDC access token. The default claim is `national_id`; its value must exactly match the unique `participants.external_reference`, which stores the participant's national ID for this link. The OIDC issuer is trusted to provide the national ID only after its identity checks. Badban does not match by name, phone, or an unverified request parameter. The national ID is not returned in the applicant API response.

Expose only a self-scoped participant identity read endpoint in this slice. The endpoint requires an active Badban identity of type `PARTICIPANT`, a non-empty trusted claim, and one exact participant record. Missing claims and unmatched records fail closed.

## Boundaries

- The identity provider must issue a verified `national_id` claim only after authenticating the participant. That external issuer configuration is not present in this repository.
- No staff-created identity links, applicant financial case data, payment information, guarantee details, or other participants' data are exposed in this slice.
- This is a prerequisite for the BL-057 applicant read model; it does not by itself complete BL-057.
- No merge, Stage, release, or production operation is authorized.
