# Sprint 22 — Reserve Policy Evaluator Foundation

- **Status:** Code + Code Review Complete / Merge Pending Explicit Approval
- **Date:** 2026-10-09
- **Stage:** Sprint
- **Scope:** BL-033 prerequisite / reserve requirement + eligibility evaluator foundation
- **Base Dependency:** Sprint 21 reserve metrics snapshot
- **Branch Strategy:** stacked on `sprint-21-reserve-metrics-snapshot`
- **Traceability:** Decision 0010 §§2-4; Decision 0048; BL-033
- **Code Authorization:** GRANTED BY DECISION 0049

## Sprint Goal

Create deterministic, versioned foundations for calculating:

1. Required Guarantee Reserve; and
2. Eligible Available Guarantee Reserve.

This Sprint does not define any production formula, percentage, threshold, liquidity haircut, reserve requirement, or eligibility rule.

## Existing Business Contract

Decision 0010 already establishes:

`Required Guarantee Reserve = Claim Liquidity Requirement + Expected Residual Loss Requirement + Stress Buffer Requirement`

and:

`Reserve Coverage Ratio = Eligible Available Guarantee Reserve / Required Guarantee Reserve`

but explicitly leaves numeric formulas and production values to versioned policy.

Sprint 22 must therefore provide only the evaluator/registry boundary.

## Reserve Metrics Boundary

Sprint 21 provides authoritative separate balances:

- reserve cash-control balance;
- reserve designated balance.

Sprint 22 must preserve them separately in evidence.

No evaluator may receive a pre-combined `reserve_available` value from Sprint 21.

## Foundation Components

Sprint 22 may add:

- `ReserveRequirementDefinitionRegistry`;
- `ReserveEligibilityDefinitionRegistry`;
- explicit versioned definition envelopes;
- typed evidence from `GuaranteeReserveMetricsSnapshot`;
- exact-decimal result validation;
- deterministic evaluator protocols;
- fail-closed unsupported/missing definition semantics;
- unit tests.

## Definition Envelope

Each executable definition must contain exactly:

- `definition_type`;
- `definition_version`;
- `payload`.

No implicit/default evaluator exists.

Unknown type/version fails closed.

## Requirement Evaluator

A requirement evaluator may return only an exact non-negative Decimal `required_reserve`.

It may not silently invent components or values absent from its versioned definition/evidence.

## Eligibility Evaluator

An eligibility evaluator may return only an exact non-negative Decimal `eligible_available_reserve`.

It must consume the separate Sprint 21 cash-control/designated balances plus explicit policy definition.

It may not use `min()`, `max()`, addition, subtraction, or another composition rule unless that rule exists in the registered versioned evaluator.

## Evidence

Requirement evaluation uses explicit named non-negative exact-decimal inputs plus non-blank authoritative input references and an evidence version. Sprint 22 does not invent producers for those metrics.

Eligibility evaluation binds to one exact `GuaranteeReserveMetricsSnapshot`:

- snapshot ID/reference;
- legal entity;
- currency;
- cash-control balance;
- designated balance;
- source fingerprint;
- metrics algorithm code/version;
- evaluated timestamp.

Cash-control and designated balances remain separate. Evidence values must be non-negative, finite exact decimals within storage limits.

## No Risk API Integration Yet

Sprint 22 does not replace Sprint 09 request inputs and does not automatically feed values into PortfolioRiskSnapshot.

That later integration requires an explicit contract selecting concrete production evaluator definitions and lineage requirements.

## Explicit Non-Goals

No production evaluator; no reserve formula; no percentage; no liquidity eligibility rule; no coverage thresholds; no Risk API integration; no draw/replenishment command; no Journal mutation; no UI; no Stage/QA/Release/Production.

## Delivery Boundary

Sprint 22 ends at Code + Code Review for evaluator foundations only.

BL-033 remains incomplete until concrete governed definitions and draw/replenishment behavior are separately authorized.
