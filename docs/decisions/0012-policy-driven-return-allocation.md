# Decision 0012 — Policy-Driven Return Allocation

- **Status:** Accepted
- **Date:** 2026-10-05
- **Scope:** Business / Financial Model / Participant Economics / Social Capital
- **Dependencies:** Decision 0003 — Asset Position Ownership by Funding Source; Decision 0008 — Policy-Driven Asset-to-Guarantee Capacity Formula; Decision 0010 — Risk Appetite and Guarantee Reserve Framework; Decision 0011 — Configurable Credit Product Rules

## Problem

The original Badban proposal defines a multi-purpose use of investment return:

- risk reserve;
- current livelihood;
- future financial support;
- capital growth;
- social reinvestment / charity.

It also states that one fixed allocation percentage is not appropriate for every participant and proposes different economic profiles based on the participant's condition.

The evolving Badban model additionally distinguishes participant-owned and program-attributed Asset Positions. Return allocation must therefore respect ownership/entitlement rights as well as social-program policy.

## Decision

Badban shall operate a versioned **Return Allocation Policy**.

Only **Eligible Net Return** may be allocated. Principal is not treated as distributable return.

The allocation process shall be:

```
Gross Economic Return
        ↓
Approved Costs / Adjustments
        ↓
Eligible Net Return
        ↓
Required Risk-Reserve Allocation
        ↓
Allocable Return
        ├─ Livelihood
        ├─ Future Financial Support
        ├─ Capital Growth
        └─ Social Reinvestment / Charity
```

The exact percentages are configurable and versioned. No universal production percentages are fixed by this decision.

## 1. Eligible Net Return

Badban must distinguish principal from return.

Conceptually:

```
Eligible Net Return
= Recognized Economic Return
- Approved Costs / Charges / Adjustments
```

Only amounts recognized under the applicable accounting and investment policy may enter the allocation engine.

Unrealized or uncertain gains must not be distributed unless the approved policy explicitly treats them as distributable.

A negative-return period must not create fictional positive allocations.

## 2. Risk Reserve Comes First

Before discretionary allocation among participant/social purposes, the applicable risk-reserve contribution is calculated under Decision 0010 and the current Return Allocation Policy.

Conceptually:

```
Allocable Return
= max(
    0,
    Eligible Net Return
    - Required Return Contribution to Risk Reserve
  )
```

The reserve contribution may vary by:

- portfolio risk state;
- reserve coverage;
- program;
- ownership/funding type;
- investment pool;
- participant segment;
- policy version.

A GREEN, AMBER, or RED portfolio state may therefore change future allocation policy prospectively.

## 3. Allocation Buckets

After the required reserve contribution, Allocable Return may be divided among four core buckets.

### A. Livelihood

Purpose:

- current participant support;
- periodic livelihood payments;
- short-term economic stability.

The policy may define:

- periodic payment amount;
- percentage of allocable return;
- minimum/maximum amount;
- carry-forward behavior when return is insufficient.

Livelihood is not guaranteed merely because an expected return was projected.

### B. Future Financial Support

Purpose:

- transition support after the participant exits or approaches exit from the support cycle;
- reducing the probability of immediate return to dependency.

Amounts in this bucket must be separately tracked.

The final vesting, withdrawal, expiry, transfer, and post-exit rules belong to the Participant Exit and Entitlement decision.

### C. Capital Growth

Purpose:

- reinvestment;
- preservation/growth of the economic base;
- increased future return capacity;
- increased future guarantee capacity where applicable.

Allocated capital-growth return becomes part of the relevant Asset Position or program capital according to its ownership policy.

Once capitalized, it is no longer treated as freely distributable return for the same period.

### D. Social Reinvestment / Charity

Purpose:

- support entry of future participants;
- grow the shared social-capital cycle;
- fund approved social-support objectives.

This bucket must remain distinct from Badban operating revenue.

Its ownership and permitted use must be explicit and auditable.

## 4. Ownership-Aware Allocation

Return allocation must respect Decision 0003.

### Participant-Owned Asset Position

Return economically attributable to a participant-owned position cannot be redirected to social reinvestment, reserve, or other purposes beyond what is explicitly authorized by:

- the participant's contract;
- the approved product/program terms;
- applicable law;
- an explicit participant election where required.

Badban must not treat participant-owned return as unrestricted program income.

### Program-Attributed Asset Position

Return attributable to a program-funded position may be allocated according to the approved program policy, subject to the participant's defined entitlement.

The system must separately identify:

- program-owned principal;
- participant entitlement;
- participant benefit allocation;
- social reinvestment;
- reserve contribution.

### Other Sponsored / Contractual Positions

Each approved ownership/funding policy must define which allocation buckets are permitted and who owns each resulting balance.

## 5. Allocation Profiles

Badban shall support configurable **Allocation Profiles** rather than one universal split.

The original business model's three participant-economic orientations are retained as policy concepts:

### BASE_SUPPORT

For participants with high current livelihood need.

Typical policy tendency:

- relatively higher livelihood allocation;
- slower capital growth;
- focus on stability.

### GROWTH_EMPOWERMENT

For participants with stronger economic-activity potential.

Typical policy tendency:

- relatively higher capital-growth allocation;
- active use of guarantee capacity;
- balance between current support and growth.

### FINANCIAL_INDEPENDENCE

For participants approaching exit from support.

Typical policy tendency:

- relatively higher future-financial allocation;
- greater emphasis on durable participant assets / transition support;
- reduced dependence on current livelihood payments.

These names describe policy profiles, not fixed percentages.

## 6. Profile Assignment

An Allocation Profile must not be guessed by the system.

Assignment must come from an approved rule or authorized decision source.

The allocation record must preserve:

- assigned profile;
- assignment reason/source;
- effective date;
- policy version;
- authorized actor/system.

Profile changes apply prospectively unless a specific policy explicitly provides otherwise.

## 7. Dynamic but Governed Allocation

Allocation percentages may differ by participant and may change over time, but only within approved policy bounds.

A policy may define:

- minimum and maximum percentage per bucket;
- mandatory reserve floor;
- mandatory/optional social-reinvestment share;
- participant choice within a permitted range;
- profile-based default recommendations;
- rebalancing frequency.

Badban must never silently modify a participant's allocation because of an opaque score or unversioned rule.

## 8. Allocation Must Balance

For every allocation event:

```
Eligible Net Return
=
Risk Reserve Allocation
+ Livelihood Allocation
+ Future Financial Allocation
+ Capital Growth Allocation
+ Social Reinvestment Allocation
+ Explicit Approved Remainder / Carry Forward
```

No unexplained residual is permitted.

Rounding differences must be handled by a documented policy.

## 9. Insufficient Return

If Eligible Net Return is below the amount expected for planned allocations, Badban must not draw from principal automatically.

The policy must specify the response, which may include:

- reduce current distributions;
- use approved carry-forward balances;
- use an explicitly permitted support fund;
- change future allocation profile;
- suspend non-mandatory allocation buckets.

Any use of principal or a separate support resource requires explicit authority and cannot be implied by this decision.

## 10. Excess Return

If return exceeds the amount needed for scheduled participant distributions, the excess must follow the applicable policy rather than becoming unclassified surplus.

Possible configured destinations may include:

- additional capital growth;
- future financial balance;
- reserve replenishment;
- social reinvestment;
- participant distributable balance where permitted.

## 11. Relationship to Guarantee Capacity

Capital Growth may increase the market value of an Asset Position and therefore may increase future guarantee capacity under Decision 0008.

However:

- the allocation engine itself does not directly create guarantee capacity;
- new capacity exists only after the resulting asset/capital value is validly recorded, valued, eligible, and pledgeable under Decision 0008.

## 12. Relationship to Risk State

Decision 0010 may constrain return allocation.

Examples of prospective policy responses:

### GREEN

Normal approved allocation profile applies.

### AMBER

Policy may increase reserve contribution or restrict optional distributions.

### RED

Policy may suspend or reduce discretionary allocations where contractually and legally permitted in order to restore required reserve strength.

Existing vested participant rights must not be silently cancelled by a portfolio risk-state change.

## 13. Participant Transparency

Participant-facing records should clearly distinguish, as applicable:

- total return attributed for the period;
- reserve contribution;
- livelihood allocation;
- future-financial allocation;
- capital-growth allocation;
- social-reinvestment allocation;
- carry-forward;
- resulting participant-owned balance;
- resulting program-attributed balance.

The participant must be able to understand that “return generated” and “cash paid now” are not the same amount.

## 14. Period and Finality

Each allocation event must define:

- allocation period;
- return measurement cutoff;
- status: draft / calculated / approved / posted / reversed;
- policy version;
- accounting reference.

A posted allocation may only be corrected through an auditable adjustment/reversal process, not silent editing.

## 15. Non-Negotiable Controls

1. Principal is not automatically distributable return.
2. Risk-reserve allocation is calculated before discretionary bucket allocation.
3. Allocation rights depend on ownership/funding policy.
4. Participant-owned return cannot be treated as unrestricted social capital.
5. No fixed universal percentage is embedded in the core product.
6. No guessed participant profile or allocation percentage.
7. Allocations must balance completely.
8. No automatic draw from principal to cover a weak-return period.
9. Capitalized return cannot be simultaneously counted as distributed cash.
10. Every posted allocation must be reproducible from source return, policy inputs, and policy version.

## Parameters Deliberately Not Fixed Here

This decision does not approve universal production values for:

- reserve allocation percentage;
- livelihood percentage;
- future-financial percentage;
- capital-growth percentage;
- social-reinvestment percentage;
- profile thresholds;
- minimum payment;
- maximum payment;
- carry-forward limit.

These values must be established in versioned program/allocation policies.

## Consequences

1. The original Badban multi-purpose return model is preserved without hard-coding one split.
2. The product can adapt allocation to participant economic condition.
3. Ownership rights remain separate from social-program policy.
4. Return allocation becomes auditable and explainable.
5. Capital growth can compound over time and later strengthen guarantee capacity.
6. Risk conditions can influence future allocations without silently rewriting historical entitlements.

## Follow-up

If Accepted, the next Business decision should define **Participant Exit and Entitlement Rules**, including:

- what happens at program exit;
- future-financial payout;
- participant-owned principal release;
- program-attributed principal recycling;
- capital-growth ownership;
- pending guarantee obligations;
- outstanding loans;
- death/incapacity/transfer scenarios where applicable.
