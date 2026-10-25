# Decision 0058 — Sprint 40 Code Authorization

- **Status:** Accepted — code scope only
- **Date:** 2026-10-25
- **Authorization:** User approved the proposed Sprint 40 plan in this conversation
- **Scope:** BL-053 — configurable multi-source external evidence registry

## Decision

Authorize Sprint 40 to implement a versioned, governed registry for read-only external evidence sources, keyed by evidence purpose and supported asset type. Multiple sources may be registered for the same purpose and asset type. Each source response must preserve its own identity, queried asset, observation time, status, evidence reference, and contract/schema versions.

The source registry is separate from source authority and business eligibility. An unconfigured source, unsupported adapter, unavailable response, stale response, malformed response, or unresolved conflict cannot be treated as valid evidence. Credentials remain environment-scoped secret references and provider-specific network destinations cannot be supplied as unrestricted URLs.

## Constraints

- No live external sources are selected or connected by this Sprint.
- No internal valuation observation is promoted to an external valuation.
- No source priority, price averaging, tolerance, freshness window, or valuation acceptance rule is invented.
- No reservation, capacity, guarantee, legal, risk, or financial state mutation is implemented.
- No Stage, QA sign-off, Release, Production, or real-money operation is authorized.
- Keep the Sprint PR Draft/Open/unmerged through implementation and Code Review; merge requires separate explicit user instruction.

## Consequences

Code may implement BL-053 within this bounded scope. Unresolved source authority and freshness inputs remain blockers to live acquisition and BL-020.
