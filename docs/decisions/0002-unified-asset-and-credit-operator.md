# Decision 0002 — Unified Asset and Credit Operator

- **Status:** Accepted
- **Date:** 2026-10-05
- **Scope:** Product / Operating Model / Financial Architecture
- **Dependency:** Decision 0001 — Configurable Asset Input

## Decision

The operating model should use a **single operating entity** for both sides of the customer flow:

1. acceptance / sale / allocation and administration of the approved asset; and
2. origination and servicing of the related loan or credit facility.

The model must therefore not depend on a structural split where Badban manages the backing asset while a separate lender is required for the core customer journey.

With Decision 0001, this rule is asset-agnostic: it applies to any approved Asset Type, not only gold.

## Target Flow

```
Customer
   ↓
Single Operating Entity
   ├─ Approved Asset Intake / Allocation
   ├─ Custody / Ownership / Valuation
   ├─ Backing & Credit Capacity
   ├─ Loan / Credit Origination
   ├─ Repayment Servicing
   └─ Release / Enforcement of Backing
```

## Consequences

1. The customer should experience one integrated financial product rather than separate asset and lending products managed by unrelated operators.
2. Asset valuation, backing availability, credit limit, disbursement, repayment and release/enforcement must share one authoritative transaction state.
3. The product architecture should still separate duties internally for governance, audit, risk and fraud control even when the legal/operating entity is unified.
4. Legal and regulatory implementation may require licensed functions, contractual delegation, segregated accounts, trustees/custodians or other controls; these implementation constraints must not be confused with the product decision to present and operate an integrated flow.
5. Any future design that reintroduces a mandatory external lender for the core model must explicitly supersede this decision.

## Rationale

The purpose is to remove operational fragmentation between the backing asset and the credit created against it. A single operator can maintain a consistent view of asset ownership, current valuation, available backing, outstanding debt and repayment status, reducing coordination gaps and simplifying the customer journey.
