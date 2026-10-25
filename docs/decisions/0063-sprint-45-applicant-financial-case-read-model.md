# Decision 0063 — Sprint 45 Applicant Financial Case Read Model

- **Status:** Code authorized for the bounded applicant read-model slice.
- **Authority:** Owner direction to complete the applicant experience and automatically scope it by national ID.
- **Backlog:** BL-057.

## Decision

Expose a read-only `/api/v1/applicant/financial-case` view for the participant resolved from the verified OIDC national-ID claim. The view joins only that participant's guarantee cases, lender loan mirrors, monthly pension entitlements, post-exit support cases, and their period entitlements.

Present financial measures in separate fields and currency buckets. Principal outstanding comes from lender loan mirrors; guarantee exposure comes from guarantee cases; realized return reported here is limited to posted return allocations for support; allocated support comes from the service funding allocations. No aggregate may combine currencies or conflate principal with return allocations.

## Boundaries

- Payment amounts are unavailable because monthly and post-exit settlement records are not implemented. Return `NOT_CONFIGURED` and null paid amounts; do not infer zero or paid status.
- External price-source status is `NOT_CONFIGURED` until a provider is configured.
- Applicant ownership is derived only from the signed OIDC claim and exact participant record match; the API accepts no caller-selected participant identifier.
- No other-participant data, internal risk material, or mutating operation is exposed.
- No merge, Stage, release, or production operation is authorized.
