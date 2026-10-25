# Sprint 40 — Configurable Multi-Source Evidence Registry

- **Status:** Code in progress; authorization recorded in Decision 0058
- **Date:** 2026-10-25
- **Backlog:** BL-053 — Configurable External Evidence Source Registry
- **Base:** current `main` plus merged PR #47
- **Scope:** Backend source configuration and read-only acquisition boundary
- **Business rules:** BL-020 answers recorded in the dossier addenda

## Sprint Goal

Allow authorized operators to configure and add multiple external evidence sources for a supported asset type and purpose, then collect each source's response through a common contract. Keep source registration separate from deciding which valuation is acceptable or whether a reservation may proceed.

## In Scope

- Versioned source definitions keyed by evidence purpose and supported asset type.
- More than one source definition may serve the same purpose and asset type.
- Source lifecycle and governance: draft, review/approval, active, suspended; configuration changes are audited and use maker-checker.
- Common provider adapter contract for source identity, queried asset identity, observation time, response state, evidence reference, and contract/schema version.
- Per-source response preservation with freshness metadata; no response overwrites another source's result.
- Environment-scoped secret references only. Provider credentials never appear in source records, API responses, logs, or evidence.
- Safe failure for unregistered, inactive, stale, unreachable, malformed, or contradictory required sources.
- An adapter can be added behind the common contract when a future provider needs provider-specific protocol handling.

## Explicitly Out of Scope

- Connecting to any live valuation, custody, collateral registry, lender, or legal authority. No source has been selected yet.
- Choosing a valuation from multiple responses, averaging prices, defining a tolerance, or deciding a risk snapshot's maximum age.
- Treating internal valuation observations as external prices.
- BL-020 reservation, backing allocation, capacity mutation, legal issuance, or any financial state change.
- Stage, QA sign-off, Release, Production, or real-money behavior.

## Acceptance Criteria

1. Governance-authorized configuration can register and list `DRAFT` sources by evidence purpose and asset type. Registration is idempotent, audited, and does not activate or call a source.
2. Multiple configured sources can be resolved for one asset type and purpose in deterministic order.
3. Each acquisition result identifies its own source, asset, observation time, status, evidence reference, and versions; errors from one source cannot be mislabeled as a successful result from another.
4. Missing or stale required responses and unresolved conflicting valuation responses are returned as not eligible; no default source, value, or GREEN/PASS is invented.
5. Provider-specific endpoints cannot be supplied as unrestricted URLs; supported adapters and outbound destinations are constrained to prevent arbitrary network access.
6. Configuration stores secret references, never secret values.
7. No reservation or other financial mutation is reachable through this capability.

Current increment: source registration/list API, persistence model/migration, and adapter contract/registry are implemented on the Sprint 40 branch. No source activation, live adapter, or durable response-observation store is included yet. Code review and CI remain pending.

## Dependencies / Open Inputs

- Existing provider-neutral source verification boundary from Sprint 36.
- The source authority, evidence format, and freshness limits remain unselected and must be supplied before live source activation.
- A separate accepted rule is required before multi-source prices can be used by capacity or reservation logic.

## DoR / DoD

Planning only. Code may start only after an explicit Sprint 40 code authorization. This proposal does not itself authorize implementation.
