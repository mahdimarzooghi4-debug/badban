# Decision 0079 — Central Identity Provider Phone OTP Integration Boundary

- **Status:** Proposed — owner approval required before implementation.
- **Date:** 2026-11-06
- **Scope:** Participant-facing phone authentication for Badban Web/API.
- **Depends on:** Accepted Technical 11 (Identity, RBAC, and Maker-Checker); Accepted Technical 12 (Security and Secrets); Decisions 0065 and 0076; Sprint 27 OIDC trust-boundary hardening; Sprint 58 automatic individual profile provisioning; Sprint 72 same-origin web/API adapter; Sprint 73 shared phone/OTP login UI.
- **Purpose:** Resolve the architectural boundary between the phone/OTP login design and Badban's existing centralized OIDC identity model without inventing an identity provider, SMS vendor, identity-proofing rule, or OTP security values.

## 1. Context and Current Facts

The accepted identity contract requires centralized OIDC/OAuth2 authentication for privileged human access and keeps password handling in the identity provider, not Badban Core. Participant access must remain self-scoped and cannot confer staff or governance authority.

The current Badban backend:
- validates bearer access tokens through the configured OIDC issuer, audience, discovery document, and trusted JWKS;
- resolves an existing Badban identity by the verified OIDC `sub`;
- creates a least-privilege PARTICIPANT identity only when the configured, trusted OIDC national-ID claim is present;
- resolves or creates the exact participant profile from that verified national-ID claim;
- keeps role grants and resource scopes independent from authentication.

Decisions 0065 and 0076 require the identity provider to verify the national ID before issuing the configured claim. Possession of a phone number is not, by itself, proof of a person's national identity, program participation, service eligibility, or authority.

Sprint 73 adds the shared phone/OTP visual flow. It deliberately does not send or verify a code because no approved OTP endpoint, provider, identity-binding rule, or OTP policy is configured.

## 2. Proposed Decision

**Recommended boundary:** Phone OTP should be an authentication factor owned and executed by the selected central identity provider (IdP), not by Badban Core.

Under this proposal:

1. Badban remains an OIDC relying party. It initiates the existing Authorization Code + PKCE flow and accepts only tokens from the configured trusted issuer.
2. The IdP owns phone enrollment and verification, OTP generation and delivery, challenge verification, resend/attempt policy, abuse controls, phone-number change and recovery, and any phone-to-person identity binding.
3. Any SMS delivery provider is selected and configured by the IdP owner. Badban does not call an SMS provider directly and does not receive SMS credentials.
4. Badban never generates, receives, verifies, stores, logs, publishes, or forwards the raw OTP.
5. A successful participant authentication must result in a trusted OIDC access token containing the stable `sub` and the configured national-ID claim only when the IdP has completed the approved authoritative identity-proofing and account-binding process.
6. Badban continues to map the identity by OIDC `sub` and the participant profile by the verified national-ID claim. A phone number is not an identity key, participant key, role key, or substitute for the national-ID claim.
7. Authentication does not grant a role. Staff, lender, supporting-institution, auditor, and governance access continue to require explicit active Badban identity and scoped role-grant authorization.
8. Privileged human identities must meet the accepted IdP MFA requirements. Participant phone OTP alone must never create or imply staff/admin privileges.

This is a proposed interpretation of the accepted centralized-identity and OIDC contracts. It is not an accepted provider selection or an authorization to implement a production OTP flow.

## 3. Proposed End-to-End Flow

```text
Browser
  → Badban Web: start OIDC Authorization Code + PKCE
  → Central IdP: hosted authentication experience
  → IdP-owned phone verification / OTP challenge
  → IdP verifies phone control and applies its approved identity-binding policy
  → IdP issues OIDC authorization code and access token
  → Badban /auth/callback
  → Badban API validates issuer, audience, signature, expiry and subject
  → Badban resolves Identity by OIDC sub
  → Participant provisioning is permitted only from the trusted national-ID claim
  → Existing server-side role grants and exact resource scopes authorize each API
```

The phone OTP proves only the factor defined by the IdP's approved policy. It does not itself establish a national identity or a Badban business entitlement.

## 4. Browser and Figma Boundary

The Sprint 73 phone and four-cell OTP screens are a design/interaction preview only. They must not be represented as an active authentication mechanism.

After the IdP is selected, the preferred way to preserve the approved visual design is to apply the design through a supported IdP-hosted login theme or an explicitly approved IdP-owned authentication extension. The OTP challenge must remain within the IdP's trust boundary.

If the selected IdP cannot safely support the required theme, the Badban UI must hand off to the IdP's hosted login experience. A Badban-owned OTP API or a browser-to-SMS-provider shortcut is not an implicit fallback.

The four visual OTP cells do not establish the production OTP length, entropy, algorithm, or policy. Those remain IdP/security decisions; the UI must conform to the approved IdP challenge contract.

No phone number or OTP may be placed in a URL, query string, browser storage, generic analytics, Badban audit event, application log, or domain event.

## 5. Token, Claim, and Identity Contract

The production integration must preserve the existing backend trust boundary:

- configured HTTPS issuer in Stage/Production;
- exact issuer and audience validation;
- trusted same-origin Discovery/JWKS behavior already enforced by the OIDC verifier;
- signature, expiry, subject, and key-ID validation;
- configured national-ID claim issued only after the IdP's approved authoritative proofing;
- no caller-supplied `national_id`, phone number, identity ID, or participant ID used to create or resolve a participant;
- no identity or profile auto-provisioning from phone possession alone;
- no role, program, service, guarantee, entitlement, or financial state inferred from successful OTP.

The current API reads the configured national-ID claim from the verified access token. The IdP integration must explicitly confirm that claim's access-token placement, name, format, and proofing semantics. An ID token or unverified user-input field is not a substitute for the claim consumed by the API.

Phone-number claims are not required by Badban's current participant-resolution path. If a future feature requires a phone number in Badban, it needs a separate data-minimization, purpose, consent, retention, and access contract.

## 6. Security Controls Required From the IdP

The selected IdP and its approved delivery provider must define and demonstrate all applicable controls before production use:

- OTP generation strength, code length/entropy, one-time use, challenge binding, and expiry;
- failed-attempt limits, resend behavior, cooldowns, and lockout/recovery behavior;
- rate limiting across the appropriate account, phone, network, device, and delivery dimensions;
- resistance to account enumeration, brute force, replay, SMS pumping, and resend abuse;
- controls and recovery procedures for SIM swap, recycled numbers, lost phones, and phone-number changes;
- authoritative national-ID proofing and the binding between that identity and the verified phone;
- staff/admin MFA and step-up authentication for privileged access;
- audit, privacy, consent, retention, support access, and incident-response controls;
- delivery-provider security, credential rotation, data processing, data residency, availability, and operational monitoring.

**No numeric TTL, code length, attempt count, resend interval, rate limit, lockout duration, or recovery rule is selected by this proposal.** These values require an explicit security/owner decision and must not be guessed in code.

## 7. Badban Responsibilities and Prohibitions

Badban remains responsible for:
- OIDC authorization-code callback handling and PKCE state integrity;
- access-token verification and trusted issuer configuration;
- identity mapping by verified OIDC subject;
- participant provisioning only from the trusted configured national-ID claim;
- deny-by-default role and resource-scope authorization;
- redacted authentication outcome logging and correlation;
- keeping access tokens out of localStorage, sessionStorage, URLs, logs, audit payloads, and domain tables.

Badban must not:
- own OTP generation, delivery, or verification under this proposal;
- store OTP challenges, OTP values, raw phone numbers, SMS provider credentials, or recovery secrets;
- infer national identity, participant identity, eligibility, or roles from a phone number;
- issue its own authentication token or create a local/mock session;
- bypass OIDC verification or role-grant checks when a phone challenge succeeds.

## 8. Decisions Still Required From the Owner

The following inputs remain explicitly unresolved:

1. **IdP product and owner:** selected IdP, hosting/deployment model, tenant, operational owner, and test environment.
2. **Participant identity proofing:** authoritative source and process for national-ID verification, initial account creation, and binding to a verified mobile number.
3. **Phone policy:** supported jurisdictions/country codes, canonicalization, number reassignment, multiple numbers, number changes, and lost-device recovery.
4. **OTP policy:** code length/entropy, expiry, attempt limits, resend/cooldown, rate-limit dimensions, lockout, anti-enumeration, and abuse/fraud controls.
5. **Delivery provider:** SMS provider, contractual owner, data residency, processing terms, sender identity, delivery monitoring, availability, and cost.
6. **Privileged authentication:** required MFA methods and step-up policy for staff and governance users.
7. **OIDC contract:** exact issuer, audience, public client, redirect URI, access-token claim mapping, national-ID claim proofing semantics, and role/claim separation.
8. **Session lifecycle:** token lifetime, refresh strategy, logout, IdP session revocation, and whether a Backend-for-Frontend/session-cookie architecture is required.
9. **Privacy and operations:** data minimization, retention, audit visibility, support recovery permissions, monitoring, incident response, and user-facing failure handling.
10. **Visual implementation:** whether the selected IdP supports the Figma-derived hosted theme and whether the final OTP length matches the four-cell design.

No value or vendor is implied by the order of this list.

## 9. Acceptance Gate Before Implementation

A later code-authorizing decision must not be proposed until the following evidence exists:

- selected IdP and an owner-approved test tenant;
- approved participant proofing and verified-phone binding contract;
- approved OTP and anti-abuse policy with explicit values;
- selected and contractually approved delivery provider, owned by the IdP integration;
- documented OIDC issuer, audience, public client, redirect URI, and trusted access-token claim mapping;
- evidence that the national-ID claim is issued only after authoritative verification;
- approved privileged-user MFA and session/revocation behavior;
- a supported IdP-hosted Figma theme or an approved alternative UX;
- real IdP-backed browser E2E and negative tests for missing claims, invalid issuer/audience/signature, expired token, unverified phone, account recovery, and authorization isolation;
- no OTP/phone leakage into Badban logs, events, audit payloads, URLs, or browser storage.

Passing this checklist does not authorize Stage, Release, Production, or real-money activity. Those remain separate gates.

## 10. Current Status and Consequences

- Sprint 73 remains a frontend preview; its phone submit and OTP verification are not active.
- No Badban OTP request/verify endpoint is authorized by this proposal.
- No IdP, SMS provider, credential, secret, database field, API, migration, event, or infrastructure resource is selected or created.
- Sprint 74 is documentation and decision-readiness only. Code remains unauthorized until this proposal is explicitly accepted and a bounded implementation scope is separately authorized.
- If the owner instead chooses Badban-owned OTP, this proposal must be revised and a separate security, privacy, identity-proofing, and operational contract must be accepted before implementation.

**Proposed outcome:** keep authentication centralized, preserve the existing OIDC trust boundary, and make phone OTP a verified IdP-owned factor rather than a new parallel identity system inside Badban.

## 11. Owner Direction: SMS and Shahkar Matching (2026-11-06)

**Owner direction received:** Badban's intended onboarding/login journey includes connecting an SMS provider for OTP and using Shahkar as a mobile-to-national-ID verification dependency. This direction records the intended capabilities; it does **not** assert that either integration is already connected or that Decision 0079 as a whole has been accepted.

### Important Shahkar contract correction

The commonly available **Shahkar matching** service accepts a **national ID and mobile number as inputs**, and returns whether they match. It does **not** normally disclose the national ID when given only a mobile number. This is a fundamental request/response distinction and must be verified against the actual selected provider's authorized API schema.

Representative public API descriptions (non-binding vendor examples; no provider selected):
- https://www.ehrazino.com/api/identity/shahkar/
- https://www.ehrazino.com/guides/what-is-shahkar/
- https://github.com/api-ir/python-sdk

Therefore, do not implement a phone-number-only `get_national_id_from_shahkar()`, a guessed response field, or an inferred national ID. If a specific licensed service contract later genuinely permits retrieving an official national identifier from a phone number, that is a **separate, explicitly reviewed and approved identity-data service contract**; it must not be silently assumed to be ordinary Shahkar matching.

### Candidate sequence for a future approved IdP integration

1. The identity provider collects the mobile number and verifies control through its authorized SMS/OTP integration.
2. The user or an **explicitly approved and independently verified identity-data source** supplies the claimed national ID; the exact collection/source workflow remains undecided. No auto-discovery from the phone number is assumed.
3. Through an approved backend-to-provider channel, the identity-proofing owner submits the mobile number and claimed national ID to the contracted Shahkar matching service. Browser direct access and exposure of provider credentials are forbidden.
4. A verified match is one necessary phone-ownership evidence signal, **not** sufficient on its own to assert a complete, authoritative identity proof. Any further identity checks and binding rules must be approved.
5. Only when the identity provider's authoritative proofing requirements are satisfied may it issue the trusted OIDC access token carrying the stable `sub` and the configured verified national-ID claim consumed by Badban.
6. Badban's existing verified-token principal resolution and role/resource authorization run unchanged. No SMS/OTP success or Shahkar match alone provisions a participant, staff grant, guarantee, entitlement, or financial state.

### Required negative and privacy tests

- National ID unknown or not authoritatively established: no trusted national-ID claim and no participant auto-provisioning from the mobile number.
- Shahkar mismatch, provider timeout, provider error, missing response, malformed response, or unverifiable provenance: fail closed; no automatic identity promotion.
- IdP challenge failure, expired/replayed challenge, invalid OTP, or unsupported phone ownership path: no successful login.
- A matched phone/national-ID pair without the IdP's required identity-proofing and stable account binding: no verified claim.
- Provider response handling must avoid leaking national IDs, full phone numbers, OTPs, credentials, raw provider payloads, or sensitive lineage into browser URLs, browser storage, general logs, audit events, analytics, and unrelated domains.
- Identity recovery, mobile-number changes, recycled SIMs, number reassignment, and staff/admin MFA require separately approved controls.

### Remaining implementation input

Before implementation, obtain the **actual authorized Shahkar provider specification** (request fields, normalized identifiers, positive/negative/unavailable semantics, provenance, retention and legal basis, credentials, access/consent constraints), the **SMS/OTP provider contract**, authoritative national-ID source/proofing rules, and the IdP's integration and OIDC-claim contract. Keep vendor selection, security numeric values, and hosting unresolved until explicit approval.

**Status:** Shahkar matching and SMS OTP are intended future integrations; their exact interfaces, sourcing, providers, policy, credentials, and operational readiness remain undecided. No code, network integration, provider purchase, service provisioning, Stage, or Production authorization is implied.
