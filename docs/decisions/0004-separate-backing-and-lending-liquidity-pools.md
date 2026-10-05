# Decision 0004 — Separate Backing and Lending Liquidity Pools

- **Status:** Proposed
- **Date:** 2026-10-05
- **Scope:** Business / Financial Architecture / Funding
- **Dependencies:** Decision 0001 — Configurable Asset Input; Decision 0002 — Unified Asset and Credit Operator; Decision 0003 — Asset Position Ownership by Funding Source

## Problem

Decision 0002 establishes one integrated operating entity for the asset and credit journey.

That does **not** answer a separate question: where does the cash used to disburse loans come from?

If the same asset position is simultaneously treated as intact collateral and consumed as the cash source for the loan, Badban risks double-counting one economic resource for two incompatible purposes.

The model therefore needs to separate:

1. the asset that creates backing / credit capacity; and
2. the liquidity that is actually disbursed as credit.

## Proposed Decision

Badban should operate two distinct economic pools under the unified operating model:

### A. Backing Asset Pool

Contains eligible Asset Positions used to create backing value and credit capacity.

Core rules:

- the asset remains tracked as an asset position;
- it is valued and revalued under its Asset Type policy;
- it can be encumbered against outstanding obligations;
- it is not automatically consumed when a loan is disbursed;
- it may be released, rebalanced, substituted, or enforced only under approved rules.

### B. Lending Liquidity Pool

Contains the cash or cash-equivalent funding available to originate and disburse credit.

Potential approved funding sources may include:

- dedicated program capital;
- operator equity or capital;
- institutional or social-investment funding;
- approved financing facilities;
- philanthropic or sponsor funding;
- recycled principal repayments;
- retained cash allocated by policy;
- other explicitly approved funding sources.

No funding source is admissible merely because it appears in this list. Each source must be approved under Badban governance and applicable legal/regulatory rules.

## Core Rule

```
Backing Capacity ≠ Lending Liquidity
```

The same operating entity may control both, but they must be separately accounted for and separately risk-managed.

## Credit Availability

A participant's actual available credit must be constrained by both collateral/backing capacity and available lending liquidity.

Conceptually:

```
Backing-Based Capacity
        ↓
Policy / Product Limits
        ↓
Portfolio / Risk Limits
        ↓
Available Lending Liquidity
        ↓
Actual Available Credit
```

A simplified conceptual rule is:

```
Actual Available Credit
= min(
    Backing-Based Capacity,
    Product / Participant Limit,
    Portfolio Risk Limit,
    Available Lending Liquidity
  )
```

The exact formula is not approved by this decision.

## Disbursement and Repayment Flow

```
Lending Liquidity Pool
        ↓
Loan Disbursement
        ↓
Outstanding Receivable
        ↓
Repayment
        ↓
Lending Liquidity Pool
```

Repayment of principal replenishes the lending liquidity pool, subject to accounting, reserve, loss, and allocation rules.

## Default Relationship

On default, Badban must follow an explicit waterfall before or during enforcement of backing.

The exact waterfall is not approved here, but the architecture must support:

- cure / collection period;
- available repayment cash;
- applicable reserves or loss buffers;
- enforcement or liquidation of backing where contractually permitted;
- repayment of outstanding principal and permitted charges;
- treatment of any surplus or shortfall according to ownership policy.

## Consequences

1. A participant's backing asset is not simply “lent back” to the participant.
2. Badban can preserve backing while still creating a revolving credit pool.
3. Asset risk and funding-liquidity risk become separate measurable risks.
4. The unified operator still provides one customer experience even though internal ledgers and control functions are separated.
5. Financial reporting must separately show:
   - backing assets;
   - encumbered backing value;
   - lending cash/liquidity;
   - loans receivable;
   - repayments;
   - reserves;
   - losses;
   - available lending capacity.
6. A credit approval does not guarantee disbursement if approved lending liquidity is unavailable.
7. Backing assets may only be sold or converted to fund credit if a future explicit product/policy decision permits that use; it is not the default.

## Rationale

Separating backing from lending liquidity prevents double use of the same economic resource and makes the model auditable.

It also preserves the product principle that one entity can manage both the asset and the loan without requiring the collateral asset itself to be consumed at origination.

## Approval Gate

If Accepted, the next Business decision should define the **Credit Product Rules**:

- how credit limits are calculated;
- tenor;
- repayment structure;
- pricing / fees, if any;
- grace periods;
- renewal / top-up rules;
- delinquency states;
- early repayment;
- and product-level eligibility.
