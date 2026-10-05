# Decision 0004 — Direct Lending Liquidity Separation

- **Status:** Proposed
- **Date:** 2026-10-05
- **Scope:** Business / Financial Architecture / Direct Lending Funding
- **Dependencies:** Decision 0001 — Configurable Asset Input; Decision 0003 — Asset Position Ownership by Funding Source; Decision 0005 — Hybrid Credit Delivery Model

## Problem

Decision 0005 establishes two credit-delivery channels:

1. the preferred external-lender / guarantee channel; and
2. optional direct lending by Badban.

The external-lender channel does not require Badban to fund the loan principal. The lender provides the lending liquidity.

If Badban itself lends, however, the cash used for disbursement must be distinct from the asset position that creates backing capacity. Otherwise the same economic resource could be double-counted as both intact backing and loan funding.

## Proposed Decision

For the **Badban Direct Lending** channel, Badban should maintain two distinct economic pools:

### A. Backing Asset Pool

Contains eligible Asset Positions used to create backing value and credit capacity.

Core rules:

- the asset remains tracked as an asset position;
- it is valued and revalued under its Asset Type policy;
- it can be encumbered against outstanding obligations;
- it is not automatically consumed when a direct loan is disbursed;
- it may be released, rebalanced, substituted, or enforced only under approved rules.

### B. Direct Lending Liquidity Pool

Contains the cash or cash-equivalent funding available for Badban-originated credit.

Potential approved funding sources may include:

- dedicated program capital;
- operator equity or capital;
- institutional or social-investment funding;
- approved financing facilities;
- philanthropic or sponsor funding;
- recycled principal repayments;
- retained cash allocated by policy;
- other explicitly approved funding sources.

No source is admissible merely because it appears in this list. Each source requires governance and applicable legal/regulatory approval.

## Core Rule

```
Backing Capacity ≠ Direct Lending Liquidity
```

This rule applies when Badban is the lender of record.

For an external lender, the equivalent separation exists across entities:

```
Badban Backing / Guarantee Capacity
        +
External Lender Funding Liquidity
        ↓
External Lender Credit
```

## Direct Credit Availability

For Badban-originated loans:

```
Actual Available Direct Credit
= min(
    Backing-Based Capacity,
    Product / Participant Limit,
    Portfolio Risk Limit,
    Available Direct Lending Liquidity
  )
```

The exact formula is not approved by this decision.

## Disbursement and Repayment Flow

```
Direct Lending Liquidity Pool
        ↓
Badban Loan Disbursement
        ↓
Outstanding Receivable
        ↓
Repayment
        ↓
Direct Lending Liquidity Pool
```

Principal repayment replenishes the pool subject to accounting, reserve, loss, and allocation rules.

## Consequences

1. External-lender loans do not consume Badban's direct-lending liquidity.
2. Badban can offer a guarantee-only model without maintaining a lending pool.
3. If direct lending is activated, funding-liquidity risk becomes an explicit Badban risk.
4. Backing assets are not automatically converted into cash to fund direct loans.
5. Badban reporting must distinguish:
   - external guaranteed exposure;
   - direct loans receivable;
   - direct lending liquidity;
   - backing assets and encumbered value;
   - reserves and losses.
6. A future policy may explicitly allow sale or conversion of some assets into lending liquidity, but that is not the default.

## Approval Gate

If Accepted, the next Business decision should define the **Credit Provider and Product Model**, including how external bank/fund products and Badban direct-credit products share one generic product framework while retaining provider-specific rules.


## Pilot Scope Note

Decision 0016 places Badban Direct Lending outside the initial pilot scope.

Therefore this decision remains **Proposed** for future direct-lending activation and does not block Technical architecture for the bounded external-lender pilot.

No production direct-lending capability may be activated until this decision and the legal/regulatory gate in Decision 0014 are separately resolved.
