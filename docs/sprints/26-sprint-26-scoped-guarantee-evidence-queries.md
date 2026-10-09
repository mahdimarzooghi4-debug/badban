# Sprint 26 — Scoped Guarantee / Backing Evidence Query

- **Status:** Code + Technical Code Review Complete / Merge Pending Explicit Approval
- **Date:** 2026-10-09
- **Code Authorization:** Decision 0053
- **Stacked base:** Sprint 24 PR #27 (contains merged Sprint 25)

## Capabilities

1. Role/Program-scoped staff GET for persisted GuaranteeCase, no mutations.
2. Separate scoped REQUESTED case evidence GET, never claims capacity or
   legal/financial eligibility; hashes visible as observation fingerprints.
3. OpenAPI typed decimal strings, IDs, versions, provider/product status,
   multi-asset ownership and exact historical valuation lineage.
4. Authentication/authorization/cross-program failure and negative-state tests.
5. Green full CI, technical code review, and exact-head evidence before exit.

## Blocked Backend Dependency Spine

- **BL-020:** executable multi-asset allocation/hold/lock policy, approved
  reservation expiry, risk snapshot qualification and freshness, legal and
  reconciliation prerequisites, atomic saga/ledger/outbox.
- **BL-016/021/023/026:** depend on real reservation and issuer/lender facts.
- **BL-033/034/038:** reserve operating policy, captured delinquency
  definition, recognized economic return/allocation rules all missing.
- **BL-027/028/029/035/036/037/039/040/045/047/052:** subsequent
  golden path and exception financial-control capabilities.
- Named real provider, legal/custody/settlement sources and production
  infrastructure are required to certify external integrations; never fake.

Backend is NOT finished by this sprint. Design/Figma remains intentionally
deferred by user direction. PR remains Draft/Open; Stage/Release not run.

## Exit Evidence

- Exact reviewed code HEAD: `b961b185d6ca9e8c297c5487b9b35486fd2e8497`
- Full code CI #426: SUCCESS after regression and authorization hardening
- [Technical Code Review](./26-sprint-26-code-review.md)
- Stacked PR #29 stays Draft/Open without Merge or Stage.
