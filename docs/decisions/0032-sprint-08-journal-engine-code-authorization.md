# Decision 0032 — Sprint 08 Journal Engine Completion; Code Authorization

- **Status:** Accepted
- **Date:** 2026-10-07
- **Scope:** Sprint 08 / Code Authorization / Bounded External-Lender Pilot
- **Depends on:** Decision 0023; Sprint 07 Code Review Complete; Technical 05, 07, 08, 11

## Decision

Accept Sprint 08 and authorize Code only for:

- **BL-030 — Append-Only Journal Engine**

The existing Sprint 03 journal foundation must be reused and hardened; no parallel ledger is authorized.

## BL-020 Readiness Decision

BL-020 — Atomic Backing Reservation is not Code-authorized.

Technical 07 §16 requires portfolio risk PASS before reservation succeeds. BL-032 is not implemented. Therefore no implicit GREEN, synthetic PortfolioRiskSnapshot, hard-coded PASS, or absent-risk bypass is permitted.

Required path:

    BL-030 → BL-032 → BL-020

## Authorized BL-030 Work

Sprint 08 may complete append-only journal hardening, exact balance and decimal validation, race-safe idempotency, linked reversal, journal read models, accepted finance read/reversal APIs, FINANCE_RECONCILIATION/AUDITOR authorization, maker-checker reversal, audit, and transactional JournalPosted/JournalReversed outbox writes.

## No Generic Posting API

No arbitrary HTTP journal creation endpoint is authorized. Journal creation remains an internal platform service invoked by domain-specific authorized workflows.

## Lineage

The journal platform must be capable of carrying accepted event, legal entity, currency, actor, correlation/causation, effective time, policy/version, template/mapping references when supplied, evidence/settlement references when required, economic-owner/domain dimensions, and reversal lineage.

No missing production value may be guessed.

## BL-031 Boundary

This decision does not authorize BL-031. No new statutory mapping, production posting template, template-selection policy, or accounting classification is invented.

## Reversal Governance

Journal reversal requires maker-checker. Maker and checker differ; approval binds to exact original journal and reversal payload/reason; stale or changed approval fails; FINANCE_RECONCILIATION initiates; checker uses an explicitly authorized governance/approval role; original posted history is never edited.

## Audit and Eventing

Journal posting and reversal are material actions. When committed, posting emits JournalPosted and reversal emits JournalReversed; audit and outbox are committed in the same transaction as journal state.

This decision does not authorize BL-041 transport/replay/dead-letter completion.

## Explicitly Unauthorized

BL-016, BL-020, BL-021, BL-031, BL-032, BL-033, BL-041 completion, generic HTTP journal posting, reservation/risk logic, provider integrations, real cash movement, production mappings/templates, Direct Lending, Stage, QA gate completion, Release Approval, Production, and real-money use remain unauthorized.

## Definition-of-Done Gate

Sprint 08 must satisfy exact balance/decimal, append-only DB, idempotency/concurrency, reversal maker-checker, read/reversal authorization, audit/outbox atomicity, OpenAPI, full CI, and Code Review requirements.

## Stage Boundary

Decision 0023 remains in force. Sprint 08 reviewed output only accumulates into the future Stage candidate.

## Approval Effect

Code is authorized only for BL-030 within the accepted Sprint 08 boundary.
