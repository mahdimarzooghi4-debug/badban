# Sprint 64 — Role-Derived Workspace Entry and Access Discovery

**Base:** PR #70 at \`4252c667682903ee02bdb56db4a7491b647f74f6\`; main \`d8b3c59ed71a93e7967d86301b72ee16cd98ddf4\`.
**Scope:** frontend integration of existing authenticated identity, active-grant and admin-workspace read contracts. No new role or authorization semantics.

## Existing approved contracts
- \`GET /api/v1/me\`: authenticated current identity.
- \`GET /api/v1/me/grants\`: only active grants whose validity window includes server current time.
- \`GET /api/v1/admin/workspace\`: descriptive role-derived admin workspace index; not an authorization grant.
- Decision 0065: PARTICIPANT identity supports the individual surface; profile creation alone does not create program eligibility.
- Decision 0066: supporting-institution access requires exact PROGRAM-scoped SUPPORT_INSTITUTION_OPERATOR grant.
- Decision 0067: lender access requires exact PROVIDER-scoped LENDER_OPERATOR grant.
- Decision 0068: admin workspaces are descriptive; protected APIs independently authorize.

## Implemented
- On successful OIDC callback, fetch current identity, active grants and admin workspace index before displaying environment choices.
- Individual environment appears only for PARTICIPANT identity.
- Institution environment appears only for exact active PROGRAM grant.
- Lender environment appears only for exact active PROVIDER grant.
- Admin environment appears only when the server workspace index contains a recognized global governance workspace or service-scoped operational workspace with its required read capability.
- Environment selection is rechecked in the click handler; manually requesting an ungranted environment is denied by the client.
- Invalid or malformed payloads fail closed. Loading and retry states are explicit; previous user's access state is not reused across tokens.
- The backend remains the authorization boundary for every protected route. The UI visibility check is navigation only.

## Boundaries
- No identity or legal-entity directory is added: the current business/privacy contract does not define which personal attributes may be disclosed to governance users.
- No organization/program creation, participant enrollment, bulk import, finance, payment or guarantee action.
- No role is inferred from email, external subject, Figma labels, browser state or user-selected environment.

## Validation
- Vitest covers identity-type mapping, exact program/provider scope, inactive/malformed grant rejection, admin workspace scope and combined access.
- Full Web Candidate CI and repository CI required on exact candidate HEAD.
