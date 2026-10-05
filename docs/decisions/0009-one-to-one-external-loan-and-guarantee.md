# Decision 0009 — One-to-One External Loan and Badban Guarantee

- **Status:** Accepted
- **Date:** 2026-10-05
- **Scope:** Business / Credit Delivery / Guarantee Amount
- **Dependencies:** Decision 0005 — Hybrid Credit Delivery Model; Decision 0006 — External Lender Integration and Guarantee Lifecycle
- **Amends:** Decision 0007 — Default, Claim, Recovery, and Loss Waterfall
- **Constrains:** Decision 0008 — Policy-Driven Asset-to-Guarantee Capacity Formula

## Decision

For the external-lender channel, the lender shall lend exactly the amount guaranteed by Badban.

The rule is:

```
External Loan Principal = Issued Badban Guarantee Amount
```

This applies to approved external credit providers, including banks, Qard-al-Hasan funds, and other approved lenders.

## Consequences

1. Badban does not provide partial principal guarantees for the standard external-lender product.
2. A guarantee of 100 authorizes a loan principal of 100, not 120, 150, or 70.
3. The lender may not disburse a principal amount that differs from the issued Badban guarantee amount.
4. If the guarantee amount changes before disbursement, the lender's approved/disbursed principal must be changed to the same amount.
5. The lender remains responsible for its own credit decision and product compliance, but the financed principal must match the Badban guarantee.
6. Fees, charges, penalties, or other amounts are not automatically included in the guaranteed amount unless an explicit future policy says otherwise.
7. Badban capacity consumption for a new external loan equals the issued guarantee amount.
8. Provider/product limits may reduce the amount Badban is willing to guarantee; once the guarantee is issued, the matching loan principal is the same amount.

## Example

If Badban issues a guarantee of 70 units:

```
Badban Guarantee = 70
External Loan Principal = 70
```

If Badban can guarantee only 40 units after applying asset, risk, and portfolio rules, the external lender may lend 40 units under this Badban-guaranteed product.

## Rationale

The purpose is to keep the relationship between backing, guarantee, and external credit simple, transparent, and fully aligned:

```
Approved Guarantee Capacity
        ↓
Issued Guarantee
        ↓
Same-Amount External Loan
```

This avoids a separate guarantee-coverage percentage in the standard Badban external-lender model and makes exposure reconciliation straightforward.
