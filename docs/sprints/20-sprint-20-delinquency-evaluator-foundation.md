# Sprint 20 — Delinquency Definition Evaluator Foundation

- **Status:** Accepted / Code Authorized
- **Date:** 2026-10-09
- **Stage:** Sprint
- **Scope:** backend foundation / BL-034 prerequisite
- **Base Dependency:** Decision 0046 contract-readiness review
- **Branch Strategy:** stacked on `planning/delinquency-contract-readiness`
- **Traceability:** Decision 0011 §12; Technical 03 ACTIVE → DELINQUENT; Technical 06 §§22-26; Technical 08 §15
- **Code Authorization:** GRANTED BY DECISION 0047

## Sprint Goal

Create the provider-agnostic, versioned delinquency-definition evaluator foundation required before BL-034 may safely mutate GuaranteeCase state.

This Sprint does **not** implement any product-specific delinquency threshold and does **not** authorize `GuaranteeCase ACTIVE → DELINQUENT`.

## Existing Business Contract

Decision 0011 already requires each Credit Product to define explicitly:

- days-past-due or equivalent thresholds;
- cure/grace period;
- lender collection obligations;
- when Badban is notified;
- when the state becomes DELINQUENT;
- claim eligibility timing;
- required evidence.

The numeric/string values remain provider/product configuration. Sprint 20 must not invent them.

## Foundation Components

Sprint 20 may implement:

1. a versioned Delinquency Definition Registry;
2. a Delinquency Evaluator protocol/contract;
3. a fail-closed resolver keyed by explicit definition type + definition version;
4. deterministic evaluation result vocabulary;
5. validation/error semantics;
6. unit tests proving unsupported/missing definitions cannot evaluate as satisfied.

## Result Vocabulary

Evaluation result is exactly one of:

- `SATISFIED`;
- `NOT_SATISFIED`;
- `INSUFFICIENT_EVIDENCE`.

`INSUFFICIENT_EVIDENCE` must never be treated as `SATISFIED`.

No score, probability, confidence threshold, fuzzy match, or AI decision is authorized.

## Definition Envelope

The foundation may require an explicit technical envelope inside `CreditProductVersion.delinquency_definition` for future executable definitions:

- `definition_type`;
- `definition_version`;
- product-specific definition payload.

The foundation must not define universal payload values.

Unknown definition type/version fails closed.

## Evaluator Contract

A registered evaluator must:

- be deterministic;
- expose explicit evaluator/algorithm version;
- consume only explicit product definition + authoritative lender evidence supplied to it;
- return one result from the exact result vocabulary;
- never perform database writes;
- never mutate GuaranteeCase, ExternalLoanMirror, Journal, Claim, Reconciliation, or Stop Controls;
- never substitute current/latest product terms for the captured product version;
- never infer missing evidence.

## Evidence Boundary

Sprint 20 does not extend the lender event schema with guessed provider fields.

The evaluator foundation may define a typed evidence input carrying existing authoritative lineage such as:

- provider/event identity;
- event type;
- event time;
- delinquency state when supplied;
- evidence references;
- provider contract/mapping/normalization versions;
- provider event sequence where supplied.

If a future evaluator requires additional evidence such as days-past-due, that field must first be added under an explicit provider/technical contract.

## Registry Semantics

Registry behavior must be deterministic:

- duplicate registration for the same definition key fails;
- unknown definition key fails closed;
- evaluator version is explicit;
- registry resolution has no network lookup;
- no runtime fallback to a default evaluator;
- no provider-specific logic is hard-coded into the registry.

## Stable Errors

Sprint 20 may introduce stable domain errors equivalent to:

- `DELINQUENCY_DEFINITION_MISSING`;
- `DELINQUENCY_DEFINITION_INVALID`;
- `DELINQUENCY_DEFINITION_UNSUPPORTED`;
- `DELINQUENCY_EVIDENCE_INSUFFICIENT`.

Exact error names may be finalized in code review, but behavior must remain fail-closed.

## Explicit Non-Goals

No concrete delinquency rule; no days-past-due value; no grace-period value; no provider state mapping; no claim timing value; no automatic product migration; no GuaranteeCase transition; no Claim creation; no Journal posting; no UI/Figma/frontend; no Stage/QA/Release/Production.

## Delivery Boundary

Sprint 20 ends at Code + Code Review for the evaluator/registry foundation only.

BL-034 remains incomplete until an accepted executable product-definition type exists and the later transition command is separately authorized.
