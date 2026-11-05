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
from high-fidelity Figma design context. Photo/logo source files must be installed as
versioned, verified local assets before claiming pixel-perfect Figma equivalence; temporary
Figma MCP asset links must never be embedded in committed source. Until then the landing
uses a CSS-safe layout without pretending it includes the exact photo.

## Product and release status

This is a **Draft PR/code candidate**, not Stage, QA approval, production-ready session
management or a real payment integration. Service request status \`RECEIVED\` is only
intake and does not create an entitlement or obligation.
