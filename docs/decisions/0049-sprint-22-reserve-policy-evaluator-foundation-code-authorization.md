# Decision 0049 — Sprint 22 Reserve Policy Evaluator Foundation; Code Authorization

- **Status:** Accepted
- **Date:** 2026-10-09
- **Scope:** Sprint 22 / BL-033 prerequisite
- **Depends on:** Decision 0010; Decision 0048; Sprint 21
- **Authorizes:** versioned reserve-requirement and reserve-eligibility evaluator foundations only

## Decision

Authorize Code for deterministic, provider-independent evaluator foundations for:

- Required Guarantee Reserve; and
- Eligible Available Guarantee Reserve.

No production rule is authorized.

## Business Boundary

Decision 0010 defines the concepts and formulas but explicitly does not approve production numeric values.

Therefore no implementation may hard-code:

- reserve percentages;
- claim-liquidity percentages;
- expected-loss assumptions;
- stress-buffer percentages;
- liquidity haircuts;
- target/warning/hard-minimum coverage thresholds;
- default reserve-eligibility composition.

## Evidence Sources

Reserve requirement evaluation uses explicit named exact-decimal input values, a versioned evidence contract, and non-blank authoritative input references. This foundation does not invent those upstream metric producers.

Reserve eligibility evaluation must originate from an exact Sprint 21 `GuaranteeReserveMetricsSnapshot`.

Cash-control and designated balances remain separate.

The foundation must not infer that either balance equals eligible reserve.

## Exact Results

Requirement evaluator result:

- `required_reserve: Decimal`

Eligibility evaluator result:

- `eligible_available_reserve: Decimal`

Both must be finite, non-negative, exact decimals within NUMERIC(38,18) bounds.

No negative or NaN/Infinity output is accepted.

## Registry Rules

For both registries:

- explicit `definition_type + definition_version` key;
- duplicate registration rejected;
- unknown key rejected;
- no fallback/default evaluator;
- explicit evaluator version required;
- no network lookup;
- no database/domain mutation during evaluation.

## Definition Envelope

Executable definitions use:

- `definition_type`;
- `definition_version`;
- `payload`.

Unexpected top-level fields fail validation.

Payload semantics belong only to the registered evaluator.

## Integration Boundary

Sprint 22 does not alter the accepted Sprint 09 Portfolio Risk API contract.

A later decision must govern how authoritative evaluator outputs replace or bind the current explicit risk-evaluation inputs.

## Explicit Non-Goals

No production evaluator; no Risk API integration; no coverage calculation wiring; no reserve draw/replenishment; no claim settlement; no Journal posting; no UI/Figma; no Stage/QA/Release/Production.

## Approval Effect

Code is authorized only for the Sprint 22 foundations above.

BL-033 remains incomplete afterward.
