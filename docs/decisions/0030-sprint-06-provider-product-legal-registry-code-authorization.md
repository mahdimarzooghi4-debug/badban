# Decision 0030 — Sprint 06 Provider/Product and Legal Authorization Registries; Code Authorization

- **Status:** Accepted
- **Date:** 2026-10-06
- **Scope:** Sprint 06 / Code Authorization / Bounded External-Lender Pilot
- **Depends on:** Decision 0023; Sprint 05 Code Review Complete; Decisions 0005, 0011, 0014; Technical 03, 04, 07, 09, 11

## Decision

Accept Sprint 06 and authorize Code only for:

- **BL-017 — Credit Provider and Product Version Registry**
- **BL-018 — Legal Entity Role and Authorization Registry**

## BL-016 Readiness Decision

BL-016 is **not** Code-authorized by this decision.

Technical 07 §14 requires authoritative reserved capacity, active exposure, other holds, and portfolio controls. These sources are not yet implemented. The system must not fabricate zero values or infer them from absence.

BL-016 remains pending until its authoritative source contracts are available.

## Provider/Product Rules

Sprint 06 may implement:

- explicit provider identity and lifecycle;
- provider activation/suspension/expiry/termination state handling;
- explicit provider/product separation;
- versioned product terms;
- immutable historical product versions/references;
- existing maker-checker and audit integration;
- accepted provider admin APIs.

It must not:

- hard-code a specific bank/fund name into core logic;
- invent production product amounts, rates, fees, tenor, grace, delinquency, or other values;
- activate Direct Lending;
- perform external provider calls.

## Legal Authorization Rules

Sprint 06 may implement:

- legal entity identity;
- regulated role registry;
- authorization/license records;
- scope, validity window, evidence, regulator/authority references;
- PENDING_VERIFICATION → VALID → SUSPENDED/EXPIRED/REVOKED/SUPERSEDED lifecycle;
- verify/suspend commands using existing authorization and maker-checker controls;
- accepted legal-authorization admin APIs.

A provider/entity must not be treated as legally authorized merely because it exists in the registry.

## Provider Activation Gate

Provider activation is high impact.

Activation must:

- be explicit;
- be audited;
- use existing maker-checker support;
- require the accepted governance authority;
- fail closed when required legal authorization is missing, invalid, expired, suspended, or out of scope.

Technical readiness does not itself activate a provider.

## Direct Lending

For this bounded pilot:

```
Badban Direct Lending = DISABLED
```

No direct-lending provider/product activation, liquidity, origination, servicing, receivable, or accounting path is authorized.

## Product Versioning Boundary

Product configuration is versioned.

Material terms are explicit; missing terms are not guessed.

Sprint 06 does not approve any production numeric values or provider-specific commercial configuration.

Future obligations must be able to capture the exact provider/product version without silent migration.

## No Financial Effect

Registry operations must not:

- reserve guarantee capacity;
- create GuaranteeCase;
- create BackingAllocation;
- create guarantee exposure;
- issue a legal guarantee;
- activate an external loan;
- post ledger entries;
- move real money.

## Explicitly Unauthorized

This decision does not authorize:

- BL-016;
- BL-019;
- BL-020;
- BL-021;
- BL-032;
- provider adapters/network calls;
- Guarantee Issuer adapter;
- lender adapter;
- issuance/activation;
- claims/recovery;
- production credentials;
- production legal authorization values;
- production product values;
- Stage;
- QA/Testing gate completion;
- Release Approval;
- Production;
- real-money use.

## Definition-of-Done Gate

Sprint 06 must satisfy the Accepted Sprint 06 plan, including:

- provider/product distinction tests;
- provider lifecycle tests;
- legal authorization validity/scope tests;
- maker-checker tests;
- direct-lending-disabled tests;
- historical/version evidence tests;
- accepted API tests;
- no-side-effect tests;
- full CI gates;
- Code Review complete.

## Stage Boundary

Decision 0023 remains in force.

Sprint 06 may be implemented and reviewed while Stage is unavailable, but its reviewed output only accumulates into the future Stage candidate.

## Approval Effect

This decision is Accepted.

Code is authorized only for BL-017 and BL-018 within the boundaries above.
