# Decision 0055 — Sprint 37 Internal Posted-Journal Source

- **Status:** Accepted — code scope only
- **Date:** 2026-10-25
- **Authorization:** User direction to complete the remaining internal-source work while unidentified external sources stay fail-closed
- **Scope:** Read-only `LEDGER` source over Badban's existing `POSTED` journal rows

## Decision

Authorize a program-scoped source adapter over persisted `JournalEntry`,
`JournalPosting`, and `JournalAccountTaxonomy` facts. The adapter may expose
exact derived balances from posted postings only, scoped by the requested
program and preserving each legal entity and the account/ownership dimensions
already stored in the journal.

The versioned source record must include `legal_entity_id`. Debit-normal
accounts derive signed balances as debit minus credit; credit-normal accounts
derive credit minus debit. `MEMO` rows retain signed debit-minus-credit control
balances. Every snapshot carries references to the contributing posted journal
entries and an exact content hash.

## Constraints

- No posted journal rows in scope means `SOURCE_UNAVAILABLE`, never an assumed
  zero balance.
- `PREPARED` entries, other programs, or inconsistent legal-entity/currency
  lineage must not be returned as valid source evidence.
- The adapter is read-only. It creates no reconciliation run/case/observation,
  journal posting, financial decision, or external provider call.
- This authorizes only the internal journal source. Guarantee issuer,
  custody, settlement, and collateral-registry sources with no named
  authoritative system remain unavailable.
- BL-020 stays blocked pending its explicit allocation, restriction/exposure,
  and risk-qualification decisions. No Stage, QA, Release, Production, or
  real-money behavior is authorized.
