# Decision 0074 — Durable External Evidence Acquisition

- **Status:** Code authorized for operator-triggered, read-only acquisition and durable per-source response history.
- **Authority:** Decision 0058 and BL-053 require independent source results with provenance and freshness metadata; the operator has asked that external valuation and restriction queries be supported.
- **Scope:** Sprint 56 adds a program-scoped operations API to query registered ACTIVE sources and preserve every returned contract independently.

## Decision

An operations user with access to the asset's program may request evidence for one asset position and evidence purpose. The system queries only registered, ACTIVE source definitions matching that asset type and purpose, in deterministic source order, through installed adapters. It stores one acquisition record and a separate immutable observation for each source response, including valid, unavailable, and invalid outcomes. A request with no active sources is recorded with zero source results.

Acquisition history is visible only to operations and audit roles authorized for the asset's program. Requests are idempotent and audited. The API returns source evidence as received under the shared contract; it does not pick a preferred valuation or resolve conflicts.

## Boundaries

- No provider, authority, credential, endpoint, or adapter is selected or installed by this Sprint.
- The current runtime adapter registry remains empty; registered sources without installed adapters return UNAVAILABLE.
- No evidence freshness threshold, price selection, GREEN status, capacity, reservation, or financial mutation is introduced.
- Only allowlisted adapter implementations can make provider calls; user-supplied URLs are not accepted.
- Stored evidence references remain opaque; raw provider payloads and secrets are not stored.
- No merge, Stage, QA release gate, Release, or Production operation is authorized.
