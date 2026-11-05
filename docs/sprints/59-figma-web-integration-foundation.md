# Sprint 59 — Figma-based Badban Web Foundation (Draft)

**Base:** \`main\` at \`d8b3c59ed71a93e7967d86301b72ee16cd98ddf4\` (CI #40503206811 success).
**Scope:** code candidate only. No Stage/QA Gate, Release Approval, Production, or merger authorized.

## Source-of-truth design nodes
- Landing: Figma \`284:3\` (8 editable sections).
- Individuals: \`160:3\`; original 24 mobile screens.
- Supporting institution: \`244:3\`; institution dashboard (17 screens).
- Lender: \`259:3\`; provider workspace (9 screens).
- Central admin: \`271:3\`; governance workspace (22 screens).

Figma mock/display numbers and labels are not authoritative. React components apply
responsive layout, not absolute screenshot positioning. Original imagery/logo assets
are separately versioned requirements and must be checked for visual equivalence.

## Integrated backend contracts
| Surface | Methods | Security/meaning |
|---|---|---|
| Individual | GET \`/api/v1/applicant/financial-case\` | Authenticated, person-derived, source data only |
| Individual | GET/POST \`/api/v1/applicant/service-requests\` | New request is strictly \`RECEIVED\`; idempotency key preserved on uncertain retries |
| Institution | GET \`/api/v1/support-institution/programs\`; GET \`/programs/{id}/beneficiaries\` | Exact program role scope, no PII or invented enrolment |
| Lender | GET \`/api/v1/lender/providers\`; GET \`/providers/{id}/guarantees\` | Provider scope, loan amount distinct from guarantee exposure |
| Admin | GET \`/api/v1/admin/workspace\` | Descriptive, non-authorizing workspace index |

## Explicit non-capabilities
Institution bulk import, employer/beneficiary deposit, consumer wallet deposit,
withdrawal, payment gateways, actual guarantee issuance/release, settlement and
release governance are NOT implemented. Disabled affordances must not suggest otherwise.
Do not infer monetary balances from disconnected read models.

## Security
- OIDC Authorization Code with PKCE. Transient code state in sessionStorage only.
- User tokens memory-only, no localStorage, no mock auth, no hardcoded credentials.
- Backend owns scope enforcement, not browser navigation.
- Fresh sign-in required after reload. Local logout is NOT server-side revocation.
- Same-origin reverse proxy /api for deployment; no token in URL or logs.
- Production requires separate approved BFF/HttpOnly session contract and security review.

## Acceptance
- TypeScript build, tests, and responsive screenshot comparison against Figma.
- Test lack-of-data and 401/403 paths, service RECEIVED-only semantics.
- Verify all static Figma assets and sizes once images are versioned.
- Keep Draft PR; do not merge or deploy on green CI alone.
