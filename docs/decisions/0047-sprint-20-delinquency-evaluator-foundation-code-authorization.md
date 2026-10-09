# Decision 0047 — Sprint 20 Delinquency Evaluator Foundation; Code Authorization

- **Status:** Accepted
- **Date:** 2026-10-09
- **Scope:** Sprint 20 / BL-034 prerequisite foundation / Code Authorization
- **Depends on:** Decision 0011 §12; Decision 0046; Technical 03; Technical 06; Technical 08 §15
- **Authorizes:** versioned delinquency definition registry/evaluator foundation only

## Decision

Authorize Code for a deterministic, provider-agnostic delinquency evaluator foundation.

This decision does not authorize any concrete delinquency threshold or any GuaranteeCase state transition.

## Business Source of Truth

Decision 0011 requires product-specific configuration for:

- days-past-due or equivalent threshold;
- cure/grace period;
- lender collection obligations;
- Badban notification timing;
- DELINQUENT state timing;
- claim eligibility timing;
- required evidence.

Those values are configuration owned by an approved Credit Product Version.

They are not defaults in core code.

## Technical Foundation

Sprint 20 may create:

- `DelinquencyDefinitionRegistry`;
- an evaluator protocol/interface;
- explicit definition key/version resolution;
- typed evidence input using existing lender-authoritative lineage;
- exact evaluation-result vocabulary;
- fail-closed exceptions/errors;
- tests.

No persistence migration is required unless Code Review proves one is necessary; the existing `CreditProductVersion.delinquency_definition` JSON field remains the product-owned storage boundary.

## Definition Key

An executable future definition must identify explicitly:

- `definition_type`;
- `definition_version`.

A product-specific payload may accompany the key.

The registry must not assume semantic meaning for payload fields it does not own.

Unsupported type/version is an error, not a fallback.

## Evaluation Result

Allowed results are exactly:

- `SATISFIED`;
- `NOT_SATISFIED`;
- `INSUFFICIENT_EVIDENCE`.

Only `SATISFIED` may ever be eligible for a later transition command, and this Decision does not authorize that command.

## Evaluator Requirements

Every evaluator must:

- be deterministic;
- have an explicit evaluator/algorithm version;
- be registered explicitly;
- use the supplied captured product definition;
- use only authoritative evidence supplied in the input;
- perform no I/O or external network request during evaluation;
- perform no database/domain mutation;
- fail closed on missing/invalid inputs.

Evaluator output must be reproducible from the same definition/evidence/effective timestamp.

## Evidence Input Boundary

The foundation may use existing normalized lender evidence fields, including:

- provider ID;
- external event ID;
- event type;
- external loan ID;
- event time / received time;
- delinquency state if supplied;
- evidence references;
- payload hash;
- provider contract version;
- adapter mapping version;
- inbound normalization version;
- provider event sequence if supplied.

No new lender field such as `days_past_due` may be invented in Sprint 20.

A future evaluator that requires new evidence must wait for a separately accepted provider-event contract.

## Registry Rules

- duplicate registration for the same type/version is rejected;
- lookup is in-process and deterministic;
- unknown type/version fails closed;
- no default evaluator exists;
- no current/latest product version lookup is performed;
- no provider-specific business rule is embedded in the registry.

## Compatibility Boundary

Sprint 20 must not retroactively reject existing stored CreditProductVersion rows merely because their current synthetic/test `delinquency_definition` does not use the executable envelope.

Product creation/activation validation must not be tightened in this Sprint unless a migration/compatibility contract is explicitly accepted.

The foundation is introduced first; executable product-definition adoption is a later governed step.

## Stable Failure Semantics

Code should expose stable fail-closed error codes for:

- missing definition key/version;
- malformed definition envelope;
- unsupported evaluator;
- insufficient authoritative evidence.

No failure path may resolve to `SATISFIED`.

## Explicit Non-Goals

No numeric threshold; no grace-period value; no provider-state mapping; no default product rule; no `days_past_due` field addition; no GuaranteeCase mutation; no Claim creation; no Journal posting; no product lifecycle migration; no UI; no Stage/QA/Release/Production.

## Approval Effect

Code is authorized only for the Sprint 20 evaluator/registry foundation.

After Sprint 20 Code + Code Review, BL-034 remains incomplete and the next gate is an explicit executable delinquency definition type plus its authoritative evidence contract.
