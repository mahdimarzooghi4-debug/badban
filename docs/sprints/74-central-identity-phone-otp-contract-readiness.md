# Sprint 74 — Central IdP Phone OTP Contract and Readiness

- **Status:** Planning proposal only; owner acceptance and Code Authorization are not granted.
- **Date:** 2026-11-06
- **Base:** Sprint 73 Draft PR #85 / `sprint-73-phone-otp-login-ui`
- **Scope:** Resolve the central identity-provider boundary for the phone/OTP login experience.
- **Related proposal:** [Decision 0079 — Central Identity Provider Phone OTP Integration Boundary](../decisions/0079-central-identity-phone-otp-integration-contract.md)

## Goal

Turn the Sprint 73 phone/OTP visual preview into an implementable, secure authentication integration plan without creating a second identity system, inventing provider policy, or bypassing the accepted OIDC and participant-identity contracts.

## Repository Findings

- Technical 11 requires centralized OIDC/OAuth2 identity and keeps password handling in the identity provider.
- Technical 12 requires bounded tokens, secure browser handling, and fail-closed trust controls.
- The existing API validates OIDC access tokens and resolves identities by verified `sub`.
- Participant identity/profile provisioning depends on the configured trusted OIDC national-ID claim; phone possession alone is not sufficient.
- Decisions 0065 and 0076 require authoritative national-ID verification by the identity provider before it issues that claim.
- Sprint 73 intentionally provides a UI preview only. No OTP service or SMS provider is configured.
- The current browser OIDC client uses Authorization Code + PKCE and keeps access tokens in memory. Local sign-out does not claim IdP logout or server-side token revocation.

## Proposed Deliverables

1. Record the proposed IdP-owned OTP boundary and the complete identity/token flow in Decision 0079.
2. Separate the responsibilities of Badban Web, Badban API, the central IdP, and the IdP's future delivery provider.
3. Record the exact unresolved owner/security decisions without assigning default numeric values or vendors.
4. Define the acceptance evidence required before a real IdP/OTP implementation can be authorized.
5. Preserve Sprint 73 as a design preview; do not make its local OTP preview appear operational.

## Explicit Non-Goals

- No Badban OTP generation, send, verify, resend, or recovery endpoint.
- No SMS provider, IdP product, test tenant, issuer, client, credentials, or secrets selected or provisioned.
- No guessed OTP length, entropy, expiry, attempt count, resend interval, rate limit, lockout, or recovery policy.
- No phone-to-national-ID mapping in Badban and no new phone field or identity key.
- No changes to OIDC verification, participant provisioning, identity mapping, role grants, authorization, or financial workflows.
- No local/mock authentication, token issuance, or bypass of OIDC.
- No database migration, domain event, API, or infrastructure deployment.
- No Stage, QA Gate, Release Approval, Production, or merge.

## Owner Decisions Required

See Decision 0079 §8. In summary: IdP selection and ownership; authoritative participant proofing and verified-phone binding; OTP/anti-abuse values; SMS delivery provider and residency; privileged MFA; OIDC claim/redirect contract; session and revocation policy; privacy/operations; and hosted-theme capability.

## Definition of Ready for a Later Code Sprint

- Decision 0079 (or its superseding decision) is explicitly accepted.
- A separate code authorization identifies a bounded implementation slice.
- A real IdP test tenant and issuer/client configuration are available.
- Verified national-ID claim semantics and phone binding are evidenced.
- OTP and anti-abuse parameters are explicitly approved.
- Privileged MFA, session/logout/revocation, and support recovery are decided.
- The Figma-derived hosted-login approach is confirmed against the selected IdP.
- Browser E2E, security negative tests, and privacy-safe observability are specified.

## Governance

- This Sprint adds only a proposed decision, planning record, and repository index entries.
- PR #86 must remain Draft/Open and stacked on PR #85.
- PRs #85 and #84 and all parents remain Draft/Open and unmerged.
- A COMMENTED technical review is not owner approval.
- No Stage, QA, Release, Production, Render provisioning, payment, transfer, settlement, or real-money action is authorized.
