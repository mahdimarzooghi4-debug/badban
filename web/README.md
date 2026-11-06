# Badban Web — Figma-to-code integration foundation

First implementation slice for the existing Badban Figma file:
- Public landing: Figma page **284:3**.
- Individual: **160:3**, with live financial case, catalogue and audited RECEIVED-only request intake.
- Supporting institution: **244:3**, provider-approved read-only programs/beneficiaries.
- Lender: **259:3**, provider-approved read-only guarantees and linked loan facts.
- Admin: **271:3**, role-derived workspace discovery only.

Nothing in this front-end creates a payment, withdrawal, guarantee, pension entitlement, capital
allocation, or program enrolment. Forms not supported by the backend stay disabled.

## Local development

1. Start the Python API (see repository root README), including PostgreSQL.
2. Copy \`.env.example\` to \`.env.local\` and set the public OIDC issuer and public client ID.
3. Register \`http://localhost:5173/auth/callback\` (and production same-origin counterpart) as an **exact**
   redirect URI with the issuer. Use Authorization Code + PKCE and a **public** client; never configure a browser client secret.
4. \`npm install\`; \`npm run dev\` from the \`web\` directory. The Vite dev server proxies \`/api\` to the API.
5. \`npm run build\`; \`npm test\`.

The browser stores bearer tokens in **memory only**, not in cookies, localStorage or persistent
storage. The code-verifier redirect state is transiently kept in sessionStorage. A refresh
requires sign-in again. Logout clears the local user only; it does **not** revoke a server
session or guarantee IdP logout. A future production-grade BFF/HttpOnly session design must
be explicitly reviewed. Production must reverse-proxy \`/api\` to the backend under the
**same origin**, configure CSP, HTTPS and identity-provider redirect origins.

Backend role checks remain the authority. No front-end role tab may confer a permission.

## Figma assets

The styling, section hierarchy, RTL, brand colors, content and navigation are implemented
from high-fidelity Figma design context. The Figma-original image-fill JPEGs and original mark are now committed as versioned local
assets. Note: the source Figma photo fills are low-resolution thumbnails, so higher-resolution
replacement and visual verification remain required before declaring pixel-perfect fidelity.
No temporary Figma asset URL is referenced by application code.

## Product and release status

This is a **Draft PR/code candidate**, not Stage, QA approval, production-ready session
management or a real payment integration. Service request status \`RECEIVED\` is only
intake and does not create an entitlement or obligation.

## Same-origin Render Stage candidate (Sprint 72)

The opt-in `Dockerfile.render-stage` compiles React and serves it through FastAPI from the exact same origin as `/api/v1/*`. `/runtime-config.js` publishes only the HTTPS issuer and **public** OIDC client ID (`BADBAN_WEB_OIDC_CLIENT_ID`). It does not supply secrets, emulate sessions or bypass the Stage Vault requirement. See `docs/sprints/72-render-same-origin-stage-adapter.md` for remaining deployment gates.
