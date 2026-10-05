# Decision 0001 — Configurable Asset Input

- **Status:** Accepted
- **Date:** 2026-10-05
- **Scope:** Product / Financial Architecture

## Decision

Badban must not hard-code gold as the only admissible asset.

Gold is an initial supported asset type, but the system shall model the input as a generic **Asset**. Any asset type that is explicitly approved by Badban policy may be configured as an admissible input.

In other words:

```
Approved Asset Type
      ↓
Asset Intake
      ↓
Valuation
      ↓
Eligibility / Haircut / Risk Rules
      ↓
Backing / Credit Capacity
```

## Consequences

1. **Gold is a configuration, not the domain model.**
2. The system must maintain an **Asset Type Registry** (or equivalent policy-controlled source of truth).
3. Each asset type may define its own:
   - valuation method and price source;
   - haircut / advance rate;
   - liquidity class;
   - custody / ownership rules;
   - revaluation frequency;
   - concentration limits;
   - eligibility status;
   - collateral / backing treatment.
4. Loan or credit capacity must be calculated from the approved valuation and risk rules of the asset, not from an assumption that the asset is gold.
5. Adding a new asset type should normally be possible through governance/configuration and policy approval, without redesigning the core product.
6. Assets not explicitly approved are not admissible inputs.

## Examples

Initial examples may include gold, cash-like instruments, fixed-income assets, fund units, or other assets approved by Badban governance. These examples do **not** mean that every such asset is automatically permitted.

## Rationale

The current model considers gold, but the intended product architecture is broader: Badban should be able to accept any asset class that the organization deliberately approves. This keeps the financial engine extensible while preserving centralized governance over risk and admissibility.
