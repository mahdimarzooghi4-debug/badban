# Sprint 27 — Technical Code Review Record

- **Status:** Technical Code Review COMPLETE; no independent human release approval
- **Date:** 2026-10-09
- **PR:** #30 Draft/Open, stacked on Sprint 26 PR #29
- **Reviewed code SHA:** `f569982389870b5afaa09d81326120cb7ac6c769`
- **Exact-head CI:** #432 SUCCESS, Quality + Secret Scan, 305 passed / 1 existing warning
- **Authority:** Technical 11 & 12 security and identity contracts; narrow BL-048 slice

## Scope and Security Boundary

The Stage/Production OIDC issuer and Discovery are required to use HTTPS,
their URL origins must match, and malformed origins, embedded credentials,
fragments, control characters, backslashes, invalid/zero ports and other
non-HTTP(S) schemes are rejected before runtime network access.

The OIDC Discovery response issuer must exactly match configured issuer.
Untrusted JWKS URLs are rejected **before** outbound HTTP requests unless
same scheme, hostname and effective port as the configured issuer. No
arbitrary private/metadata-server or cross-origin retrieval is permitted
through JWKS injection. Redirect-following is explicitly disabled on both
Discovery and JWKS reads, including externally injected HTTP clients that
default to following redirects.

Malformed JSON shapes generate stable fail-closed errors rather than letting
untrusted response types crash the verification flow. Existing RS256
signature, token Issuer/Audience, subject, expiry and key-ID validation remain
intact. Unknown key IDs require a new fetch from the same trusted origin
and cannot silently authorize an unknown signature.

Development/test may intentionally use HTTP issuer **only** within
configuration's explicit same-origin boundary. No provider name,
credential, issuer address, exception threshold or real Production
configuration was invented.

## Regression Evidence

- Positive signed RS256 token with trusted key.
- Negative signature, issuer, audience, expiration and not-yet-valid token.
- Eight+ origin injection variants including scheme downgrade, metadata
  service address, cross-host, port switch, userinfo, fragments and port zero.
- Malformed or null Discovery/JWKS documents: stable negative codes;
  HTTP redirect cannot be followed even by redirect-enabled client.
- Key rotation via unknown kid refreshes JWKS from trusted origin.
- Production/Stage rejects HTTP OIDC, foreign Discovery, embedded
  credentials, malformed and zero ports; correct HTTPS same-origin passes.
- All baseline backend tests continue to pass.

## CI Failure and Resolution Trace

- #428: initial code (the subsequent URL-parser correction was applied to
  the same bounded technical scope).
- #429: Ruff formatting failure in two new blocks, fixed.
- #430: 301 tests passed, 2 tests failed because httpx mock with
  `json=None` emits an empty response instead of JSON `null`.
  The test fixture now supplies actual JSON `null`, exercising the
  expected malformed-object handling without changing production logic.
- #431: full SUCCESS before final zero-port validation addition.
- #432: final exact-code CI SUCCESS, 305 tests passed, Quality and Secret Scan.

## Residual Risks / Not Claimed

Application URL-origin checks do **not** replace Production TLS identity
verification, network egress policy, DNS-rebinding controls, firewalls,
monitoring, Keycloak/enterprise OIDC deployment, or runtime integration
with an approved Vault implementation. Cross-origin JWKS hosts have
no implicit exception: a legitimate provider with hosted keys on another
origin requires an explicit accepted trust contract before it is supported.

BL-048 is **NOT DONE**: actual provider secret/key rotation, real provider
webhook authenticity/nonces, production credentials, MFA/session/revocation
verification, deployment isolation, penetration testing, and release
security gates remain open.

This review does not authorize a business-state command or operational
Production. BL-020 reservation and its dependent golden path remain
blocked on approved policy, authoritative exposure/risk, legal/valuation
and atomic multi-asset allocation semantics.

`Code = COMPLETE`

`Technical Code Review = COMPLETE`

`Merge/Stage/QA/Release/Production = NOT AUTHORIZED`
