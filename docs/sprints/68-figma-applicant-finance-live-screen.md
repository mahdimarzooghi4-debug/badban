# Sprint 68 — Figma Applicant Finance Live Read Screen

**Status:** Draft UI implementation on top of Sprint 67. Not merged or deployed.
**Design:** Figma Badban file `ubJTK7Vt3lwSEeVdjyn59n`, node `163:160`, Mobile / Finance • Visual (390×844).
**Backend:** existing, owner-scoped `GET /api/v1/applicant/financial-case` from Sprint 45 / Decision 0063.

## Delivered

- Mobile-first Persian RTL finance page with matching heading, navy hero, 2×2 metric-card layout, financial detail accordions and bottom-tab icons.
- Figma's exact native icon frames exported via Plugin API as 11 **versioned local SVGs**, not 7-day temporary Figma URLs or replacement symbols. Original logo asset already exists and is reused. SVG root dimensions are preserved.
- Mobile applicant topbar uses original brand asset and Figma notification pictogram. The pictogram makes **no** claim of a live notifications API; the brand remains an accessible switch to the environment picker.
- Currency-specific 4-field financial summaries: external-loan outstanding principal, guarantee exposure, net posted return allocated to support, and allocated support. No cross-currency sum and no approximate “million” conversions.
- Real backend guarantee records, monthly pension entitlements, post-exit cases and period entitlements are exposed read-only behind native details/summary controls.
- Lender mirror states are labeled `RECORDED` vs `NOT_RECORDED`, not verified. The guarantee detail response contains no distinct loan currency; its lender mirror amount is intentionally shown **without** a currency label. The true currency buckets are on the summary.
- Payment and external price status remain `NOT_CONFIGURED`; “APPROVED” entitlement is not depicted as paid. A capital-management CTA only opens an explanatory no-payment/no-deposit disclosure.
- Supports missing and multi-currency values, without fabricating zero or total record counts; API list limit is 100.

## Verification and open gates

- New Vitest view tests cover exact-decimal formatting, separate currency buckets, no sample/demo values, missing records, unverified lender mirror and payment limitations.
- Python API/UI contract tests verify each SVG exists, parses, preserves Figma native width/height and has a real UI callsite; all assets stay within the repository.
- Exact-head GitHub Web Candidate CI and full CI are required, then a technical COMMENTED review.
- Real configured OIDC browser E2E, live API integration, screenshot-based visual parity against Figma, accessibility/browser testing, Stage/QA, Release Approval and Production are **not** completed by this slice.
- The backend and ledger are unchanged, and no real deposit, withdrawal, settlement, entitlement decision or guarantee decision is activated.
- Keep all stacked PRs Draft/Open and unmerged until explicit user approval.
