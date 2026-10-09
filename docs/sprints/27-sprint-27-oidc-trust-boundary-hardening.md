# Sprint 27 — OIDC Trust Boundary Hardening

- **Date:** 2026-10-09
- **Status:** Code / Technical Review pending full exact-head CI
- **Scope:** BL-048 identity/security correctness slice; no provider credential rotation
- **Base:** Sprint 26 PR #29, Draft/Open
- **Accepted Contract:** Technical 11 and Technical 12 §§8, 14, 18, 21, 35, 38, 41

## Implementation

- Validate complete OIDC issuer/discovery origins (no credentials,
  fragments, control characters or malformed port).
- Require HTTPS issuer and discovery in Stage/Production; explicitly
  configured development/test HTTP remains possible on the same origin.
- Reject a JWKS URL in the Discovery document unless it shares the
  trusted configured issuer origin, including scheme and port. Refuse
  cross-host, metadata-service, downgrade and userinfo attempts without
  an outbound fetch.
- Disallow following discovery/JWKS HTTP redirects even when an
  injected HTTP client is configured to follow them.
- Reject malformed Discovery/JWKS shapes with stable fail-closed errors.
- Preserve RS256, issuer/audience/expiry verification and trusted
  unknown-kid JWKS refresh/rotation.

## Important Limits

- This is a source-level outbound URL trust boundary, not a substitute
  for Production DNS pinning, TLS trust, network egress allowlisting,
  Keycloak/OIDC configuration, MFA, revocation and secret-store readiness.
- No provider-specific cross-origin JWKS exception is defined; an issuer
  that genuinely uses a different origin will require an explicit
  reviewed trust contract and controlled allowlist before integration.
- No Stage/Production infrastructure, credential, vendor or business
  decision is fabricated.
- Other BL-048 obligations (live secret rotation, provider signatures,
  replay/security pen-testing) remain incomplete.
- No financial mutation, risk approval, reserve, API bypass, Merge,
  Stage, QA, Release, Production or Figma.
