# Decision 0035 — Sprint 10 Product Account Taxonomy and Posting Templates; Code Authorization

- **Status:** Accepted
- **Date:** 2026-10-07
- **Scope:** Sprint 10 / Code Authorization / Bounded External-Lender Pilot
- **Depends on:** Decision 0015; Decision 0033; BL-030 complete; Technical 04; Technical 05

## Decision

Accept Sprint 10 and authorize Code only for:

- **BL-031 — Product Account Taxonomy and Posting Templates**

## Rationale

BL-031 is Ready because its product-level account classes, canonical account codes, ledger layers, no-posting rules, posting-template semantics, versioning requirements, and legal-entity mapping boundary are already defined by Accepted Technical 04 and Technical 05.

BL-020 — Atomic Backing Reservation is not included in Sprint 10. Its implementation still requires explicit, non-invented contracts for deterministic multi-Asset Position allocation, reservation-expiry derivation, and risk-snapshot freshness/qualification semantics. Those ambiguities must not be converted into code assumptions.

## Authorized BL-031 Work

Sprint 10 may implement:

- the stable Badban product account taxonomy from Technical 05;
- relational persistence for the product account taxonomy required by Technical 04;
- relational legal-entity account mapping records required by Technical 04;
- immutable/versioned internal posting-template specifications matching the already accepted Technical 05 semantics;
- internal resolution/validation helpers for product accounts, template references, legal-entity mappings, and historical version references;
- explicit distinction between monetary, memorandum/control, and external-mirror semantics;
- tests proving that reservation, legal guarantee issuance, external lender disbursement, repayment at the lender, delinquency, claim submission/rejection, and collateral-release events do not invent Badban cash/revenue/loan-receivable postings;
- tests proving historical template references remain explicit and no statutory account mapping is guessed when missing.

## No Invented Statutory Mapping

No statutory chart code, legal-entity account mapping, production posting rule, legal accounting classification, or production policy value may be seeded or inferred.

The accepted Badban product taxonomy is product-level only. A missing legal-entity mapping must fail or remain explicitly unmapped; it must never be guessed.

## API Boundary

No generic HTTP posting endpoint is authorized.

BL-031 remains an internal financial-platform capability. Existing journal read/reversal APIs remain unchanged.

## BL-020 Boundary

BL-020 remains not Code-authorized by this decision.

Sprint 10 must not implement BackingAllocation, reservation expiry, capacity locking, REQUESTED → RESERVED, or portfolio-risk consumption logic.

## Stage / Release Boundary

Decision 0033 remains active. This Sprint does not claim Stage, QA/Testing, Release Approval, Production, or real-money readiness.

## Approval Effect

Code is authorized only for BL-031 within the Sprint 10 boundary.
