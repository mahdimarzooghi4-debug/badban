# Decision 0019 — Product Backlog Complete for Bounded Pilot; Sprint Planning Authorized

- **Status:** Accepted
- **Date:** 2026-10-05
- **Scope:** Governance / Stage Gate / Scrum Product Backlog
- **Dependencies:** Decision 0018; Product-Backlog Stage Completion Review

## Decision

Badban's Scrum/Product Backlog stage is complete **for the bounded external-lender pilot scope defined in Decision 0016**.

The project is authorized to move to the next planning stage:

```
Scrum/Product Backlog → Sprint Planning
```

This decision does **not** authorize Sprint execution or Code by itself.

## Accepted Backlog Baseline

The accepted backlog package contains:

- an ordered bounded-pilot Product Backlog;
- P0/P1/P2/P3 priorities;
- technical enablers;
- dependency order;
- candidate delivery slices;
- Definition of Ready;
- Definition of Done;
- explicit no-code and production gates.

The backlog preserves traceability to Accepted Business and Technical contracts.

## Ordering Principle

Implementation must establish correctness prerequisites before dependent financial workflows.

The accepted high-level order is:

```
Foundation / Stack / Persistence
→ Identity / Authorization
→ Participant / Asset / Valuation
→ Policy / Capacity / Risk
→ Provider / Legal Registry
→ Guarantee Request / Reservation
→ Legal Issuance
→ External Loan Activation
→ Ledger / Financial Controls
→ Repayment / Release
→ Claim / Recovery
→ Return / Entitlement
→ Exit
→ Reconciliation / Workspaces
→ Security / Recovery Hardening
→ End-to-End Golden Path
```

This is dependency ordering, not a requirement that each capability occupy its own Sprint.

## Sprint Planning Authorization Boundary

Sprint Planning may now:

- select the first Ready backlog slice;
- define a Sprint Goal;
- select exact backlog items;
- resolve implementation technology choices required by that Sprint;
- define acceptance tests;
- define Sprint non-goals;
- identify external/stubbed dependencies;
- produce a Sprint Backlog.

If BL-001 stack choices are unresolved, Sprint Planning may make them the explicit first Sprint/enabler outcome.

## Definition-of-Ready Gate

No implementation item may enter Sprint execution unless it satisfies the accepted Definition of Ready, including applicable:

- Business clarity;
- Technical traceability;
- acceptance/rejection paths;
- authorization;
- idempotency;
- policy/version behavior;
- persistence/migration semantics;
- security;
- observability;
- tests;
- dependency readiness.

Financial/high-impact work additionally requires explicit failure atomicity, ledger/control effect, reconciliation, and maker-checker semantics.

## Code Gate

This decision does not itself authorize Code.

Code begins only after an explicit Sprint plan is accepted for the selected Ready work.

The first Sprint must remain within the bounded pilot and may not imply:

- Direct Lending;
- real-money provider certification;
- unapproved numeric Policy Pack values;
- unvalidated legal authority;
- invented statutory accounting mappings.

## Production Gate

Real-money activation remains blocked by Decision 0016 and later stages:

```
Sprint
→ Code
→ Code Review
→ Stage
→ QA/Testing
→ Release Approval
→ Production
```

Named counterparties, legal/provider validation, production Asset Type, numeric Policy Pack, accounting mappings, collateral path where required, participant disclosures, security/operational readiness, and Release Approval remain mandatory later gates.

## Consequence

The repository's next active work is **Sprint Planning**.

Current parent-process status:

```
Business ✓
→ Technical ✓
→ Scrum/Product Backlog ✓
→ Sprint Planning
→ Sprint
→ Code
→ Code Review
→ Stage
→ QA/Testing
→ Release Approval
→ Production
→ Monitoring
→ Improvement
```
