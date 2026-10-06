# Sprint 05 — Deterministic Guarantee Capacity Calculator

- **Status:** Accepted
- **Date:** 2026-10-06
- **Stage:** Sprint Planning
- **Scope:** bounded external-lender pilot
- **Entry Gate:** Decision 0023; Sprint 04 Code + Code Review Complete
- **Depends on:** BL-011, BL-012, BL-014 complete through Code Review
- **Code Authorization:** GRANTED BY DECISION 0029

## 1. Sprint Goal

Deliver the pure deterministic guarantee-capacity calculation core required before any reservation or exposure mutation is allowed.

Sprint 05 contains only:

- **BL-015 — Deterministic Guarantee Capacity Calculator**

The calculator must be deterministic, exact-decimal, versioned, replayable from captured inputs, and must not reserve capacity, create guarantee exposure, post ledger entries, or infer missing policy values.

## 2. Dependency Readiness

The selected item is dependency-ready:

- BL-011 Asset Position and Ownership/Funding Classification — completed in Sprint 02;
- BL-012 Immutable Valuation Observation — completed in Sprint 03;
- BL-014 PolicyResolver and DecisionSnapshot — completed in Sprint 04.

BL-016 and BL-032 remain outside this Sprint.

## 3. Accepted Calculation Architecture

The calculator implements the accepted Decision 0008 / Technical 06 architecture:

```
Gross Market Value
= Eligible Quantity
× Approved Price
× Approved FX Conversion, when applicable

Pledgeable Market Value
= Gross Market Value
× Pledgeable Fraction

Position Backing Capacity
= Pledgeable Market Value
× Advance Rate

Gross Backing Capacity
= Sum(Position Backing Capacity)

Available Guarantee Capacity
= max(
    0,
    Capped Gross Backing Capacity
    - Reserved Guarantee Capacity
    - Active Guarantee Exposure
    - Other Approved Capacity Holds
  )
```

## 4. Explicit Inputs Only

Sprint 05 must not discover or invent policy values.

The calculator receives explicit immutable inputs including, where applicable:

- eligible quantity;
- approved price;
- approved FX conversion;
- valuation observation ID and freshness evidence;
- pledgeable fraction;
- advance rate;
- exact Policy Pack/component version IDs;
- capped gross backing capacity supplied by an explicitly approved upstream cap/control result;
- reserved guarantee capacity;
- active guarantee exposure;
- other approved capacity holds;
- effective timestamp;
- algorithm version.

No implicit `latest`, default Advance Rate, default pledgeable fraction, guessed FX, guessed cap, or production numeric policy value is allowed.

## 5. Portfolio/Cap Boundary

Sprint 05 does **not** implement BL-032 Portfolio Risk Snapshot/Gate or invent concentration rules.

Therefore:

- per-position capacity is calculated deterministically;
- uncapped gross backing capacity may be summed deterministically;
- final available capacity may consume an explicit `capped_gross_backing_capacity` input;
- the calculator must not derive unknown concentration/portfolio caps by itself;
- a missing required cap/control input must not be replaced by the uncapped value silently.

This preserves the accepted separation between deterministic capacity arithmetic and future portfolio-risk/cap policy evaluation.

## 6. Valuation Freshness

Only accepted valuation evidence may contribute to new capacity.

The application service must use existing immutable ValuationObservation semantics:

- `FRESH` may contribute when otherwise valid;
- `STALE` creates no new capacity;
- expired `valid_until` creates no new capacity;
- missing/guessed valuation is prohibited.

The calculator must preserve the valuation observation ID in the material decision evidence.

## 7. Decimal and Rounding Rule

All capacity arithmetic uses Python `Decimal` / exact database numeric semantics only.

Sprint 05 introduces **no implicit quantization or rounding** inside the calculator.

Rule:

- calculations preserve exact Decimal results;
- binary floating point is forbidden;
- no currency-scale rounding is silently applied;
- downstream monetary quantization, if later required, must use a separately accepted explicit rounding rule;
- algorithm version remains separate from policy version.

This rule prevents Sprint 05 from inventing an unapproved production rounding policy.

## 8. Algorithm Version

The calculator exposes an explicit algorithm version.

Initial code may define a stable calculator version identifier for the implemented arithmetic contract.

Changing material calculation semantics requires a new algorithm version; historical DecisionSnapshots retain the version used.

## 9. DecisionSnapshot Integration

A successful material capacity calculation must be capturable through the existing Sprint 04 DecisionSnapshot service with:

- decision type;
- exact Policy Pack/component IDs;
- algorithm code/version;
- material input payload;
- material output payload;
- valuation observation IDs;
- effective timestamp;
- actor/system;
- reproducible hashes.

Sprint 05 must not create a generic public DecisionSnapshot write endpoint.

## 10. Pure Calculator Boundary

The calculator must not:

- reserve capacity;
- mutate Asset Position;
- mutate ValuationObservation;
- create GuaranteeCase;
- create BackingAllocation;
- create active guarantee exposure;
- post journal entries;
- perform provider/lender calls;
- perform legal authorization;
- perform portfolio risk decisions;
- release backing;
- infer missing data.

It returns calculation results only.

## 11. Validation

At minimum, calculation input validation must enforce:

- all monetary/quantity inputs are Decimal, not float;
- eligible quantity is non-negative;
- approved price is non-negative;
- approved FX conversion, when required, is positive;
- pledgeable fraction is within `[0,1]`;
- Advance Rate is within `[0,1]`;
- reserved/exposure/hold values are non-negative;
- capped gross backing capacity is non-negative;
- capped gross backing capacity must not silently exceed the uncapped gross backing capacity unless a future accepted contract explicitly permits that behavior;
- stale/expired valuation contributes no new capacity.

Invalid inputs fail closed and must not create financial side effects.

## 12. Acceptance Tests

Tests must prove:

- exact Decimal arithmetic;
- no float path;
- gross market value formula;
- pledgeable market value formula;
- position backing capacity formula;
- multi-position uncapped gross sum;
- final available capacity subtraction and floor at zero;
- stale valuation produces no new capacity;
- expired valuation produces no new capacity;
- missing required FX/cap/control input does not silently default;
- fractions outside `[0,1]` fail;
- negative exposure/reservation/hold inputs fail;
- same exact inputs + same algorithm/policy versions reproduce the same result;
- result carries algorithm and policy-version evidence;
- DecisionSnapshot captures the calculation without fresh external lookup;
- calculation creates no reservation, guarantee exposure, journal posting, or provider effect.

## 13. Definition of Done

Sprint 05 Code is Done through Code Review only when:

- BL-015 calculator contract is implemented;
- tests above pass;
- format/lint/type/security/dependency/container CI gates are green;
- no implicit latest policy path exists;
- no production numeric policy values are introduced;
- no BL-016/BL-032/provider/legal/guarantee/lending work is introduced;
- Code Review completes.

Stage remains Deferred under Decision 0023.

## 14. Explicit Non-Goals

Sprint 05 does not implement:

- BL-016 Guarantee Capacity Read Model;
- BL-032 Portfolio Risk Snapshot/Gate;
- Provider/Product Registry;
- Legal Entity Authorization Registry;
- GuaranteeCase request/reservation/issuance;
- BackingAllocation reservation;
- lender integration;
- claims/recovery;
- return allocation;
- participant-exit financial reconciliation;
- Direct Lending;
- production policy values;
- Stage;
- QA/Testing gate completion;
- Release Approval;
- Production;
- real-money use.

## 15. Approval Effect

This Sprint 05 plan is Accepted.

Decision 0029 grants Code authorization only for BL-015 under the boundaries above.
