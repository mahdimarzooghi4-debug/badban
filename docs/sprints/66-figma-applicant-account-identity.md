# Sprint 66 — Figma Applicant Account and Identity Read Integration

**Status:** Code candidate. Stacked on Draft PR #76; do not merge/release.
**Design reference:** Figma Badban account `163:239` and identity `174:145` within file `ubJTK7Vt3lwSEeVdjyn59n`.

## Backend contract

Read only: authenticated `GET /api/v1/applicant/participant` from Sprint 44. The route binds the record to the verified OIDC subject's trusted national-ID claim and returns **only** participant UUID and persisted lifecycle status. The GET never creates a participant. Missing/ineligible profiles return an error; the frontend must not POST/create implicitly.

## Implemented

- Account tab and identity detail use an authenticated, owner-bound API read and strict whitelist `participant_id` / `lifecycle_status`.
- Figma sample name, profile code and demo internal record ID are replaced with the actual UUID and literal persisted status. No national ID, OIDC subject, personal name, phone, device count, banking details, or invented verification claims.
- Stale responses are suppressed on token changes; loading/errors show no old identity.
- The finance shortcut navigates only to the existing authenticated financial-case read view, not a capital transfer action.
- View is responsive RTL using existing Badban tokens; no new backend contracts or lifecycle changes.

## Verification

Vitest covers self-scoped GET, malformed status/UUID, data allowlist/privacy, missing token and 404. TypeScript/Vite and full CI are required on the exact SHA. Figma screenshot parity, real OIDC-browser E2E and deployed runtime are **not yet proven**.

**Release boundaries:** keep Draft/Open, no Stage/QA/Release/Production or financial behavior without explicit approval.
