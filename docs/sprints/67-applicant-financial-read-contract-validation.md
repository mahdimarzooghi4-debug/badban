# Sprint 67 — Applicant Financial Read Contract Validation

**Status:** Read-contract hardening candidate, stacked on Draft PR #77.
**Design reference:** Figma Applicant Finance `163:160`.
**Backend source:** Sprint 45, Decision 0063, `GET /api/v1/applicant/financial-case`.

## Implemented in this slice

- Correct the web TypeScript contract to match the full persisted Sprint 45 response: guarantee cases, external-loan mirror status, monthly entitlements, post-exit cases and nested entitlements, currency-scoped balances, and explicit external payment/price-source states.
- Validate authenticated participant UUID, known persisted state vocabularies, timezone-aware timestamps, UUIDs, unique record IDs, bounded list lengths and unique currency buckets.
- Preserve exact monetary precision. Decimal strings (including exponent notation emitted by Decimal values such as `0E-18`) are normalized as strings without JavaScript floating-point conversion.
- Fail closed on paid amounts or payment states when settlement remains `NOT_CONFIGURED`; require lender mirror state to agree with `RECORDED` / `NOT_RECORDED`.
- Whitelist the financial response fields; no national ID, OIDC subject, bank account, risk material or other extraneous metadata is passed into the view model.
- Route the existing financial panel through the validated reader; this slice does not create a new API or mutate financial state.

## Explicit business boundaries

- Each currency remains a separate bucket; no cross-currency sum.
- Guarantee exposure, lender-reported outstanding principal, realized posted support return allocations and allocated support remain distinct measures.
- A recorded lender mirror is not described as independently verified.
- Paid amounts remain null; external price and payment sources remain `NOT_CONFIGURED`.
- The existing API returns bounded lists (up to 100) without a pagination/total-count contract. Do not present returned list lengths as total historical counts.
- No deposit, withdrawal, payment, guarantee approval, entitlement approval or ledger mutation is implemented.

## Remaining work and gates

This PR is data-contract validation only, not the completed Figma Finance screen. The visual screen `163:160` still requires the exact Figma static assets to be copied into versioned local files and verified. The Figma asset URLs are temporary; this runtime could not resolve `www.figma.com` via curl, so no remote asset URL or substitute icon is committed. Continue with the exact assets when transfer is available.

Exact-head Web CI and full CI plus COMMENTED technical review are required. Real OIDC browser E2E, Figma screenshot parity, Stage/QA and release approval remain separate gates.

Keep Draft/Open. No merge, Stage, QA, Release or Production operation is authorized.
