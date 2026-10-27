# Sprint 56 — Durable External Evidence Acquisition

## Goal

Complete the provider-neutral evidence acquisition slice by exposing a program-scoped operations command and preserving independent source responses.

## Deliverables

- Add an idempotent, operations-authorized acquisition endpoint for an asset position and evidence purpose.
- Query only matching registered ACTIVE sources using the installed adapter registry.
- Persist an acquisition record and each source's result independently, including unavailable/invalid outcomes.
- Expose paginated acquisition history to authorized operations and auditors.
- Record correlation, timestamps, result status, evidence reference, contract/schema versions, and relevant typed facts.
- Add constraints, indexes, migration, audit events, and Decision 0074.

## Boundaries

- No live source or adapter is configured or connected.
- An empty adapter registry yields UNAVAILABLE results and never a quote or passing status.
- No averaging, default source choice, freshness threshold, eligibility decision, reservation, or financial state change.
- Do not persist raw provider payloads or secret values.
- No merge, Stage, QA release gate, Release, or Production operation is authorized.
