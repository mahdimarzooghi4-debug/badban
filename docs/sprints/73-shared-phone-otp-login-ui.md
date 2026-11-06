# Sprint 73 — Shared phone/OTP login UI

**Status:** Draft code candidate stacked on Sprint 72 / PR #84. No merge, Render resource creation, Stage admission, QA, release, or deployment.

## Scope delivered
- Add a responsive React authentication page at the existing same-origin `/app` entrypoint, matching the approved Badban Figma authentication page (desktop/mobile; phone and OTP states).
- Reuse the original Badban logo asset in a white rounded logo container on mobile and desktop.
- Replace the old landing-page direct OIDC button action with navigation to the shared login page. All app and panel entry points use the same page; no role is selected before authentication.
- Add a reusable four-cell OTP input with Persian/Arabic numeral normalization, paste distribution, focus advance, and Backspace navigation.
- Keep the existing OIDC PKCE path available as an explicitly secondary route only when its public issuer/client configuration exists.
- Provide a development-only OTP visual preview at `/app?auth-preview=otp`; the preview clearly states that no code was sent and disables verification.

## Explicit authentication boundary
The repository currently has an OIDC access-token verifier and browser PKCE client, but no Badban phone-OTP request/verify endpoint and no configured SMS/OTP provider. This Sprint does **not** invent an endpoint, provider, OTP lifetime, rate limit, attempt count, phone-to-identity binding, or token-issuance behavior. The phone form reports that code delivery is not configured; the four-cell screen is only a local development preview until the real identity/OTP contract is approved and provisioned. No fake code, mock session, or local authentication is introduced.

## Exclusions
- No SMS gateway/provider, OIDC issuer/client, credentials, database, server, Render service, or billing resource is created.
- No payment gateway, payment, transfer, settlement, or financial operation.
- No backend authorization, identity, role-grant, or principal behavior is changed.
- No access token is stored in localStorage or sessionStorage; the existing OIDC PKCE memory-only token behavior is unchanged.
- No Stage, QA, Release Approval, Production, or merge.

## Validation
- Vitest covers Persian/Arabic digit normalization, phone formatting, four-cell paste distribution, bounds, Backspace behavior, and immutability.
- Web Candidate CI runs TypeScript/Vite build and Vitest.
- Full CI remains required on the exact Sprint 73 head.
