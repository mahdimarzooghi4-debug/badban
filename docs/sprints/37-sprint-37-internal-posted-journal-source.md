# Sprint 37 — Internal Posted-Journal Source

- **Status:** Implemented and merged to `main` via PR #44 on 2026-10-25; exact-head CI #495 and combined CI #510 passed
- **Date:** 2026-10-25
- **Decision:** [0055 — Internal Posted-Journal Source](../decisions/0055-sprint-37-internal-posted-journal-source.md)
- **Base:** Sprint 36 PR #40 (`sprint-36-verified-source-acquisition`)
- **Backlog:** BL-042 internal ledger/sub-ledger source only

## Objective

Connect the versioned source-acquisition boundary to Badban's existing
append-only posted journal facts, preserving program and legal-entity scopes.

## In scope

- Version the ledger source record to include its actual legal-entity dimension.
- Read only posted journal entries and their taxonomy in the requested program.
- Derive exact per-account/per-owner balances from debit and credit postings.
- Preserve contributing journal-entry references and content hash.
- Return `SOURCE_UNAVAILABLE` when no posted evidence exists; never synthesize
  a zero balance.
- Reject mismatched legal entity, currency, account taxonomy, or program lineage.

## Explicitly out of scope

- Any external source, provider connection, credential, or synthetic provider.
- Reconciliation comparison, policy selection, case/run persistence, or
  financial mutation.
- Reservation and allocation policy (BL-020), including its dependent
  reservation/issuance/activation flows.
- Stage, QA completion, Release, Production, and real-money behavior.

## Acceptance

- Only `POSTED` facts for the exact program are returned.
- Legal-entity and account dimensions remain distinct in the snapshot.
- The digest validates and references every contributing journal entry.
- Missing rows fail closed as unavailable rather than being treated as zero.
- Keep the PR Draft/Open/unmerged until exact-SHA CI and code review complete.
