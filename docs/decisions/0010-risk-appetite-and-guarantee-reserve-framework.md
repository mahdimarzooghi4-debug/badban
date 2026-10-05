# Decision 0010 — Risk Appetite and Guarantee Reserve Framework

- **Status:** Accepted
- **Date:** 2026-10-05
- **Scope:** Business / Risk / Portfolio Governance / Guarantee Reserve
- **Dependencies:** Decision 0007 — Default, Claim, Recovery, and Loss Waterfall; Decision 0008 — Policy-Driven Asset-to-Guarantee Capacity Formula; Decision 0009 — One-to-One External Loan and Badban Guarantee

## Problem

Badban now has rules for:

- converting approved assets into guarantee capacity;
- issuing one-to-one guarantees for external loans;
- handling delinquency, claims, recovery, and residual loss.

The next business requirement is to define how much aggregate guarantee risk Badban is willing to carry and how much reserve/liquidity must exist before new guarantees may be issued.

Asset backing reduces loss risk, but it does not eliminate:

- claim-timing risk;
- asset-price decline;
- enforcement delay;
- execution-cost risk;
- operational failure;
- concentration risk;
- residual shortfall after collateral recovery.

Badban therefore needs an explicit portfolio-level risk appetite.

## Decision

Badban shall operate a versioned **Risk Appetite Policy** that governs the entire guarantee portfolio.

The policy must separately control:

1. **Exposure Appetite** — how much guarantee exposure may exist;
2. **Concentration Appetite** — how concentrated that exposure may be;
3. **Claim Liquidity** — how much immediately available liquidity is needed to settle approved claims;
4. **Loss Absorption** — how much reserve/capital is available for residual covered losses;
5. **Stress Resilience** — whether Badban can continue operating under adverse scenarios.

No new guarantee may be issued when any hard risk gate is breached.

## 1. Guarantee Exposure Base

Badban must track at least:

```
Total Active Guarantee Exposure
= Sum(Active Issued Guarantee Exposure)
```

and separately:

```
Total Reserved Capacity
= Sum(Valid Unexpired Reservations)
```

Risk appetite may apply limits to active exposure, reservations, or their combined committed amount.

Because Decision 0009 requires one-to-one lending:

```
External Loan Principal
= Issued Badban Guarantee Amount
```

the active guaranteed principal can be reconciled directly to the active guarantee exposure.

## 2. Reserve Architecture

Badban should distinguish three reserve/capital functions even if governance later chooses to hold them in one legally combined pool.

### A. Claim Settlement Liquidity

Purpose: pay approved lender claims on time before recovery from the underlying asset is completed.

This reserve must be held in assets that satisfy an approved liquidity standard.

### B. Expected Loss Reserve

Purpose: absorb statistically expected residual losses after borrower recovery and collateral enforcement.

This reserve reflects the quality and observed performance of the guarantee portfolio.

### C. Stress / Capital Buffer

Purpose: absorb unexpected losses and protect continuity under severe but plausible stress.

This buffer should not be treated as ordinary operating cash.

## 3. Reserve Requirement

The exact numeric formula is not fixed by this decision, but the required reserve must be derived from versioned policy inputs.

Conceptually:

```
Required Guarantee Reserve
= Claim Liquidity Requirement
+ Expected Residual Loss Requirement
+ Stress Buffer Requirement
```

Where policy may use inputs such as:

- total active guarantee exposure;
- guaranteed portfolio delinquency;
- historical default frequency;
- historical recovery rate;
- collateral volatility;
- collateral liquidity;
- time-to-enforcement;
- provider concentration;
- Asset Type concentration;
- macroeconomic stress assumptions.

The system must preserve the input set and policy version used to calculate every reserve requirement.

## 4. Reserve Coverage Ratio

Badban shall calculate:

```
Reserve Coverage Ratio
= Eligible Available Guarantee Reserve
  / Required Guarantee Reserve
```

The Risk Appetite Policy defines at least:

- target level;
- warning level;
- hard minimum level.

No production numeric percentages are approved by this decision.

## 5. Exposure Utilization Ratio

Badban shall calculate a portfolio utilization measure:

```
Guarantee Utilization
= Committed Guarantee Exposure
  / Approved Portfolio Exposure Limit
```

Committed exposure may include both active guarantees and specified reservations according to policy.

The policy defines:

- normal operating range;
- warning threshold;
- stop-new-issuance threshold.

## 6. Concentration Limits

Risk appetite must support configurable limits by at least:

- Asset Type;
- lender / credit provider;
- credit product;
- geographic/program segment where applicable;
- participant;
- custodian;
- issuer or underlying asset issuer;
- currency;
- maturity bucket;
- liquidity class.

A portfolio may be fully collateralized and still be unacceptable if it is excessively concentrated.

## 7. Risk States

Badban should expose one authoritative portfolio risk state:

### GREEN

All hard limits satisfied and reserve coverage above the approved target/warning boundary.

New guarantees may be issued subject to normal participant/product checks.

### AMBER

One or more warning thresholds are breached, but hard minimums remain satisfied.

Policy may:

- reduce new issuance;
- tighten advance rates for future capacity;
- require additional reserve funding;
- restrict specific providers or Asset Types;
- require governance review.

### RED

A hard limit or minimum reserve requirement is breached.

Badban must block new guarantee issuance that would increase exposure until the breach is cured or an explicitly authorized emergency policy applies.

Existing guarantees remain governed by their issued terms.

## 8. Stop-Issuance Gate

Before every new guarantee issuance, Badban must validate both:

1. participant-level available guarantee capacity under Decision 0008; and
2. portfolio-level risk appetite under Decision 0010.

Conceptually:

```
Issue Guarantee
only if
Participant Capacity PASS
AND
Provider/Product Rules PASS
AND
Portfolio Risk Appetite PASS
```

A participant having sufficient collateral does not override a portfolio-level RED state.

## 9. Dynamic Policy Response

Risk appetite may change prospectively when portfolio conditions deteriorate.

Allowed prospective responses may include:

- lower Advance Rates for new capacity;
- tighter concentration caps;
- higher reserve requirements;
- suspension of a provider/product;
- suspension of a specific Asset Type for new guarantees;
- shorter reservation validity;
- stricter revaluation frequency.

Policy changes must not retroactively rewrite valid issued guarantee terms unless the applicable contract explicitly permits such action.

## 10. Stress Testing

Badban must support periodic stress testing.

Stress scenarios should be able to model combinations such as:

- simultaneous asset-price decline;
- higher default frequency;
- lower recovery rates;
- longer enforcement periods;
- multiple claims arriving in a short interval;
- concentration failure at a major lender/custodian/Asset Type;
- liquidity disruption.

Stress testing must estimate at least:

- projected claims;
- projected recovery;
- reserve draw;
- residual loss;
- liquidity shortfall;
- resulting portfolio risk state.

## 11. Reserve Eligibility

Not every asset held by Badban counts as guarantee reserve.

A reserve asset must satisfy an approved reserve-eligibility policy covering:

- legal availability;
- absence of conflicting encumbrance;
- liquidity;
- valuation reliability;
- custody/control;
- currency compatibility;
- concentration limits.

Participant-owned backing assets must not be counted as general guarantee reserve merely because Badban controls or encumbers them.

## 12. Reserve Replenishment

The Risk Appetite Policy must define approved reserve replenishment sources.

Potential sources may include:

- allocated investment returns;
- guarantee-related fees where legally/permissibly charged;
- sponsor/program contributions;
- institutional capital;
- recoveries;
- retained surplus allocated by governance;
- other explicitly approved sources.

Listing a source does not itself authorize it.

## 13. Reserve Draw and Recovery Accounting

When an approved claim is settled from reserve:

- the reserve draw must be recorded separately from final economic loss;
- later collateral/borrower recoveries must be traced against the related claim;
- recovered amounts replenish the appropriate reserve/accounting layer according to policy;
- unresolved recovery receivables remain visible until closure.

This preserves Decision 0007's distinction between claim liquidity and final loss.

## 14. Governance

Risk appetite must be approved by the designated Badban governance authority.

At minimum, governance must approve:

- exposure limits;
- concentration limits;
- reserve methodology;
- warning and hard thresholds;
- stress scenarios;
- reserve eligibility;
- emergency override authority.

Emergency overrides must be:

- explicit;
- time-bounded;
- reason-coded;
- auditable;
- incapable of silently changing historical policy records.

## 15. Non-Negotiable Controls

1. Participant collateral sufficiency alone is not enough for issuance.
2. Portfolio RED state blocks new exposure growth.
3. Reserve assets and participant backing assets are separate concepts.
4. Reserve requirement and reserve availability must be independently calculated.
5. No guessed recovery/default assumptions in production calculations.
6. Every risk decision must use an explicit policy version.
7. Existing issued guarantees remain contractually stable unless validly amended.
8. Reserve draw, recovery, and final loss must remain separately measurable.
9. Concentration limits apply even when individual exposures are fully backed.
10. Risk metrics must be reproducible and auditable.

## Parameters Deliberately Not Fixed Here

This decision does not set production numbers for:

- reserve percentages;
- target coverage ratio;
- warning thresholds;
- hard minimums;
- maximum portfolio exposure;
- concentration limits;
- stress assumptions;
- recovery assumptions;
- default assumptions.

Those values require governance approval based on pilot data, legal structure, actual asset behavior, provider contracts, and observed portfolio performance.

## Consequences

1. Badban gains a portfolio-level brake independent of participant-level collateral.
2. Reserve planning becomes measurable rather than discretionary.
3. Claims can be paid without confusing settlement liquidity with final loss.
4. Growth in guarantee volume becomes conditional on capital/reserve strength.
5. Risk policy can tighten prospectively without redesigning the product.
6. Future dashboards can expose GREEN / AMBER / RED portfolio status and the drivers behind it.

## Follow-up

If Accepted, the next Business decisions should define:

1. Credit Product Rules;
2. Return Allocation Policy;
3. Participant Exit and Entitlement Rules;
4. Direct Lending Liquidity Model, if the optional direct-lending channel is activated.
