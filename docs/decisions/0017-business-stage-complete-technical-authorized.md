# Decision 0017 — Business Stage Complete for Bounded Pilot; Technical Stage Authorized

- **Status:** Accepted
- **Date:** 2026-10-05
- **Scope:** Governance / Stage Gate / Product Development Process
- **Dependencies:** Decision 0016 — Pilot Boundary and Initial Policy-Pack Governance; Business-Stage Completion Review

## Decision

Badban's Business stage is complete **for the bounded external-lender pilot scope defined in Decision 0016**.

The project is authorized to move to the next parent-process stage:

```
Business → Technical
```

This authorization does not approve real-money pilot activation or production.

## Basis

The Business-Stage Completion Review found the accepted business decisions internally consistent for the bounded pilot.

The pilot scope has explicit business rules for:

- configurable assets;
- ownership/funding;
- valuation and guarantee capacity;
- external lender integration;
- guarantee lifecycle;
- one-to-one loan/guarantee matching;
- risk appetite and reserve controls;
- credit-product configuration;
- delinquency, claim, recovery, and loss allocation;
- return allocation;
- participant exit and entitlement;
- regulated legal-role separation;
- accounting/sub-ledgers;
- pilot boundaries and stop conditions.

## Future-Scope Exception

Decision 0004 — Direct Lending Liquidity Separation remains Proposed.

It does not block Technical architecture because Decision 0016 explicitly excludes Badban Direct Lending from the bounded pilot.

Technical implementation must not implement or infer direct-lending behavior for the pilot.

## Technical Authorization Boundary

Technical architecture may now define:

- system context and trust boundaries;
- domain aggregates;
- state machines;
- data models;
- ledger architecture;
- policy/versioning model;
- APIs/events;
- provider adapters;
- reconciliation;
- identity/access control;
- auditability;
- observability;
- failure/retry/idempotency behavior;
- deployment/security architecture.

Technical design must remain inside the accepted Business contracts.

## Production Gate

Real-money pilot activation remains blocked until all Decision 0016 activation gates are satisfied, including:

- named validated lender;
- named validated Guarantee Issuer;
- validated asset/custody path;
- approved numeric Pilot Policy Pack;
- legal sign-off for the selected structure;
- accounting mappings;
- required external collateral registration;
- Stage / QA / Release Approval.

## Consequence

The next repository stage is **Technical**.

No Code/Sprint work should begin before the Technical stage is sufficiently defined and translated into the Scrum/Product Backlog.
