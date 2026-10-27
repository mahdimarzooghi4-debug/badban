# Decision 0073 — Governed External Evidence Source Lifecycle

- **Status:** Code authorized for maker-checker activation and suspension of registered evidence sources.
- **Authority:** Decision 0058 requires configurable multi-source acquisition without selecting a live provider or valuation authority.
- **Scope:** Sprint 55 governs source lifecycle transitions for valuation, restriction, and encumbrance sources.

## Decision

A registered source remains DRAFT until an independent global governance approver reviews an ACTIVATE request. Active sources may be suspended through a separately requested and approved lifecycle change. Every request and decision records a reason reference and audit event. The requester cannot approve or reject their own request.

Activation changes only the source's configuration lifecycle state. It does not certify the source as authoritative, select it for valuation, or make a reservation eligible. A source without an installed runtime adapter continues to return an unavailable result.

## Boundaries

- Source credentials remain secret references and are not returned by the API.
- No live provider is selected, connected, or called by this Sprint.
- No price selection, freshness threshold, GREEN status, reservation, or financial mutation is introduced.
- No merge, Stage, release, or production operation is authorized.
