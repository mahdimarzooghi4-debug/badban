# Sprint 65 — Figma Applicant Request History and Evidence-Only Detail

**Status:** Code candidate, stacked on Draft PR #75; not merged or released. 
**Design:** Figma Badban file \`ubJTK7Vt3lwSEeVdjyn59n\` nodes \`163:81\` ("Mobile / Requests") and \`173:2\` ("Mobile / 11 — Request details").
**Backend owner:** Sprint 57 authenticated participant-owned \`GET /api/v1/applicant/service-requests\`.
**Rule:** No new API endpoint, service state machine or financial action.

## Implementation

- Replace static first-page request rendering with server-backed, exact 25-row pagination and the backend's optional \`service_code\` filter. No caller-supplied participant ID.
- Enforce exact requested \`limit\`, \`offset\`, optional service code, bounded rows, unique UUIDs, timezone-aware timestamps and **RECEIVED-only** status before rendering.
- Filtering, pagination and refresh instantly suppress prior-scope response data; owner token and requested page are bound to UI state.
- The request detail screen is derived solely from the selected, validated **list row**. There is no individual-request detail endpoint. Only type, request ID, submission date and RECEIVED state are presented as facts.
- Use original Badban typography, navy/gold tokens and responsive RTL layout. No Figma demo IDs, names, dates, amounts or approval are used.
- After a submit response, validate the returned RECEIVED record and reload the authorized list instead of appending an unverified/local row. Preserve the original idempotency key on uncertain response.
- Avoid displaying approval, financial allocation, payment, or a review outcome where no backend contract exists.

## Testing and gates

Vitest tests for exact self-scoped paths, filters, offsets, response shape, duplicate IDs, wrong-service responses, invalid IDs and timestamps, non-RECEIVED status, denial and malformed input.

Required before acceptance: exact-head web build/test, full CI (format, lint, mypy, migrations, backend tests, dependency audit, container build), COMMENTED technical review. **Not yet independently verified:** real OIDC issuer/browser E2E, screenshot parity for both Figma frames, and actual integration with a running deployment. Do not mark such checks as passed solely on unit/CI.

Keep Draft/Open. No merge, Stage, QA Gate, Release Approval, Production, real-money action or change to authorization policy without explicit authorization.
