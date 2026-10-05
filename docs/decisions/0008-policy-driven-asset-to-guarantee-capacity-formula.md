# Decision 0008 — Policy-Driven Asset-to-Guarantee Capacity Formula

- **Status:** Proposed
- **Date:** 2026-10-05
- **Scope:** Business / Risk / Asset Valuation / Guarantee Capacity
- **Dependencies:** Decision 0001; Decision 0003; Decision 0005; Decision 0006; Decision 0007; Decision 0009

## Problem

Badban needs one deterministic and auditable way to convert approved Asset Positions into usable guarantee capacity without assuming that the asset is gold or that every asset uses the same risk percentage.

## Proposed Decision

Badban shall calculate capacity through a versioned policy pipeline. Capacity is measured in units of **guarantee exposure**, not directly as loan principal.

### 1. Canonical risk parameter

Each Asset Type policy defines one canonical **Advance Rate**:

```
0 <= Advance Rate <= 1
Advance Rate = 1 - Haircut
```

Only one canonical value drives the calculation; “haircut” may be a display representation.

### 2. Market value

For each Asset Position:

```
Gross Market Value
= Eligible Quantity
× Approved Price
× Approved FX Conversion, when applicable
```

The calculation must preserve the Asset Type, quantity, price source, valuation timestamp, currency, FX source when needed, and policy version.

Missing, invalid, or stale valuation creates no new guarantee capacity.

### 3. Pledgeable value

Not all economically owned or attributed value is necessarily available as backing.

```
Pledgeable Market Value
= Gross Market Value
× Pledgeable Fraction
```

Pledgeability is determined by ownership/funding policy, legal restrictions, existing liens, withdrawal restrictions, and approved controls.

### 4. Position backing capacity

```
Position Backing Capacity
= Pledgeable Market Value
× Advance Rate
```

Ineligible, suspended, frozen, legally unavailable, or non-pledgeable positions create zero **new** capacity. Existing encumbrances are not automatically released.

### 5. Portfolio and concentration limits

When multiple positions are used, Badban applies versioned limits such as:

- maximum contribution from one Asset Type;
- issuer, custodian, currency, or liquidity-class concentration;
- participant/program limits;
- stress or liquidity buffers.

These controls cap capacity; they do not silently rewrite market value.

### 6. Gross and available capacity

```
Gross Backing Capacity
= Sum(Eligible Risk-Adjusted Position Capacities)
  subject to approved caps
```

```
Available Guarantee Capacity
= max(
    0,
    Capped Gross Backing Capacity
    - Reserved Guarantee Capacity
    - Active Guarantee Exposure
    - Other Approved Capacity Holds
  )
```

Reservation and encumbrance must prevent double use of the same backing.

### 7. External loan principal equals issued guarantee

Under Decision 0009, the standard external-lender product uses one-to-one principal matching:

```
External Loan Principal
= Issued Badban Guarantee Amount
```

Therefore the external-lender channel does not use a separate guarantee-coverage percentage for principal.

A request may proceed only when the intended loan principal can be fully matched by available Badban guarantee capacity and all provider/product/program limits.

Example only: if Badban has 70 units of approved available guarantee capacity and issues a guarantee of 70, the external lender lends 70 units of principal.

### 8. External lender and direct lending

For an external lender, actual credit depends on both lender approval and sufficient Badban guarantee capacity.

For Badban Direct Lending, future direct-lending policy must additionally constrain disbursement by available lending liquidity.

### 9. Revaluation

Active backing is revalued at the frequency defined by Asset Type policy.

Revaluation may change unused capacity and the risk status of active exposure, but it must never retroactively increase an issued guarantee beyond its approved terms.

### 10. Capacity deficiency

If revaluation makes backing insufficient under the applicable threshold, the exposure enters **Capacity Deficiency**.

Policy may then:

- freeze new guarantees;
- require top-up;
- permit asset substitution;
- reduce unused reservations;
- use an approved buffer;
- require cure actions;
- permit enforcement only where contractually and legally allowed.

A market-price decline alone must not trigger an unconfigured liquidation.

### 11. Stale-price safety

If the authoritative valuation is unavailable or too old:

- new capacity from that position is blocked;
- existing encumbrance remains;
- the position enters a valuation-risk state;
- no guessed fallback price is allowed.

### 12. Multiple assets

A guarantee may be supported by one or more Asset Positions, but Badban must preserve the exact allocation of capacity from each position to each reservation or active guarantee.

This allocation is required for revaluation, substitution, release, enforcement, and surplus calculation.

### 13. Release

Capacity is released only through an authoritative lifecycle event such as:

- reservation expiry/cancellation;
- confirmed eligible repayment for a declining guarantee;
- valid guarantee reduction;
- settlement;
- claim/recovery closure.

Time passing by itself does not release capacity.

### 14. Versioning

Every reservation and guarantee issuance must preserve effective versions of:

- Asset Type policy;
- ownership/funding policy;
- valuation policy;
- provider policy;
- credit product policy;
- concentration/portfolio policy;
- guarantee coverage rule.

### 15. Non-negotiable controls

1. No valuation → no new capacity.
2. No eligibility → no new capacity.
3. No pledgeability → no new capacity.
4. No double reservation or encumbrance.
5. No guessed prices.
6. No retroactive increase of issued guarantee exposure from later price gains.
7. No silent increase from lender-side loan changes.
8. No release without authoritative lifecycle evidence.
9. Every capacity result must be reproducible from immutable inputs and policy versions.
10. Asset Type determines valuation/risk treatment; ownership type determines rights and pledgeability.

## Parameters not fixed by this decision

This decision does not approve production numbers for:

- advance rates / haircuts;
- concentration caps;
- valuation frequency;
- stale-price windows;
- stress buffers;
- participant/provider/product limits.

Those values must be versioned policy approved through Badban governance.

## Consequences

- Gold becomes one configuration, not a special-case formula.
- New Asset Types can be added without redesigning the engine.
- Standard external-lender loans use one-to-one principal-to-guarantee matching.
- Multiple assets can support one participant subject to policy.
- Falling values reduce unused capacity and may create deficiency without rewriting existing contractual guarantees.
- Capacity remains deterministic, auditable, and explainable.

## Follow-up

If Accepted, the next Business decisions should define:

1. Risk Appetite and Reserve Sizing;
2. Credit Product Rules;
3. Return Allocation Policy;
4. Direct Lending Liquidity Model, if that optional channel is activated.
