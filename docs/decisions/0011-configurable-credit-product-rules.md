# Decision 0011 — Configurable Credit Product Rules

- **Status:** Accepted
- **Date:** 2026-10-05
- **Scope:** Business / Product / Credit Products / Provider Integration
- **Dependencies:** Decision 0005 — Hybrid Credit Delivery Model; Decision 0006 — External Lender Integration and Guarantee Lifecycle; Decision 0008 — Policy-Driven Asset-to-Guarantee Capacity Formula; Decision 0009 — One-to-One External Loan and Badban Guarantee; Decision 0010 — Risk Appetite and Guarantee Reserve Framework

## Problem

Badban can now determine available guarantee capacity and connect that capacity to external banks and Qard-al-Hasan funds.

The product still needs one generic business model for representing different lender products without hard-coding the rules of a particular bank, fund, or direct-lending product.

Different providers may define different:

- minimum and maximum amounts;
- tenor;
- repayment schedule;
- pricing / fee rules;
- grace periods;
- eligibility criteria;
- delinquency thresholds;
- early-settlement rules;
- renewal and top-up rules.

Badban must support these differences while preserving the one-to-one rule:

```
External Loan Principal = Issued Badban Guarantee Amount
```

## Decision

Badban shall maintain a versioned **Credit Product Registry**.

Every credit product used through Badban must be an explicitly approved product configuration associated with exactly one lender of record.

The same generic product model shall support:

- external banks;
- Qard-al-Hasan funds;
- other approved external lenders;
- Badban Direct Lending, when enabled.

## 1. Product Identity

Every Credit Product must define at least:

- product identifier;
- lender / provider identifier;
- lender of record;
- product name;
- product type;
- active / suspended / retired state;
- effective-from date;
- optional effective-to date;
- policy version.

A retired or suspended product cannot accept new guarantee requests, while existing obligations remain governed by their captured terms.

## 2. Product Amount Rules

Each product must define:

- minimum principal;
- maximum principal;
- allowed increments / rounding rules;
- applicable currency;
- participant/program/provider limits.

For an external-lender product:

```
Requested Loan Principal
<= Available Badban Guarantee Capacity
```

and after approval / issuance:

```
Issued Badban Guarantee Amount
= External Loan Principal
```

Badban may have more available capacity than the participant chooses to use. The guarantee issued for a transaction is only the amount of that approved loan.

## 3. Approval Flow

A standard external-lender transaction follows:

```
Participant Request
      ↓
Product Eligibility
      ↓
Badban Available Guarantee Capacity
      ↓
Portfolio Risk Gate
      ↓
Lender Credit Approval
      ↓
Final Approved Principal
      ↓
Badban Guarantee Reservation / Issuance
      ↓
Lender Disbursement of Exactly the Guaranteed Principal
```

The exact operational order may vary by provider integration, but the final state must satisfy the same invariants.

No lender disbursement may activate a Badban-guaranteed transaction if principal and issued guarantee amount differ.

## 4. Tenor

Each product must explicitly define its permitted tenor model, such as:

- fixed tenor;
- allowed tenor range;
- provider-selected tenor from an approved set.

Badban must store the actual accepted tenor in the immutable transaction terms snapshot.

No default tenor may be guessed when the provider response is missing.

## 5. Repayment Structure

The product must define its supported repayment structure, including as applicable:

- installment frequency;
- number of installments;
- principal repayment method;
- first payment date rule;
- final maturity rule;
- grace period;
- balloon or residual payment, if permitted.

Badban must retain the authoritative schedule or an authoritative schedule reference supplied by the lender.

## 6. Pricing, Fees, and Charges

The lender/product policy must explicitly define all permitted pricing components.

These may include, where legally and contractually applicable:

- interest / profit rate;
- service fee;
- administrative fee;
- insurance or third-party charge;
- late-payment charge;
- other approved charges.

Badban must not infer or invent a charge.

For external lending, lender-originated pricing remains the lender's product term and must be captured in Badban for transparency and reconciliation.

Guarantee coverage of non-principal amounts is **not automatic**. Under Decision 0009, the standard one-to-one rule applies to loan principal. Any guarantee of fees or other charges requires a separate explicit future policy.

## 7. Eligibility

A Credit Product may define eligibility conditions such as:

- participant/program membership;
- age or legal-capacity conditions where applicable;
- minimum/maximum guarantee amount;
- required Asset Type or backing class;
- minimum remaining program term;
- prior repayment behavior;
- provider-specific criteria;
- geographic or operational availability.

Eligibility must be explicit and versioned.

Badban must not infer eligibility from missing information.

## 8. Guarantee Exposure Mode

Each product must declare one of the supported guarantee-exposure modes:

### FIXED

The issued guarantee amount remains encumbered until an approved release or reduction event.

### DECLINING

Guarantee exposure and encumbered capacity may decline as authoritative eligible principal repayment is confirmed.

The initial rule remains:

```
Original Loan Principal = Original Issued Guarantee Amount
```

The product policy defines how subsequent repayment affects guarantee exposure.

## 9. Early Repayment

Each product must define the treatment of early repayment.

At minimum, Badban must know:

- whether early repayment is allowed;
- whether charges apply;
- authoritative settlement amount;
- when the lender considers the loan fully settled;
- when the guarantee may be reduced or released.

Badban releases backing only after authoritative lender settlement confirmation and its own guarantee reconciliation.

## 10. Top-Up / Increase

A lender must not increase the principal of an existing Badban-guaranteed obligation unless Badban first approves additional capacity.

A top-up requires:

1. fresh participant capacity calculation;
2. portfolio risk gate;
3. product/provider eligibility;
4. new or amended guarantee approval;
5. updated immutable terms snapshot;
6. lender confirmation that the resulting principal equals the resulting guarantee amount.

A lender-side unilateral increase creates no additional Badban guarantee exposure.

## 11. Renewal / Refinance

Renewal or refinance is treated as a new credit decision unless an explicit product policy defines a controlled amendment path.

Badban must ensure:

- old exposure is closed or explicitly migrated;
- new capacity is available;
- no duplicate guarantee remains unintentionally active;
- new terms and policy versions are captured.

## 12. Delinquency Rules

Each product must define:

- days-past-due or equivalent thresholds;
- cure/grace period;
- lender collection obligations;
- when Badban is notified;
- when the state becomes DELINQUENT;
- claim eligibility timing;
- required evidence.

These product-specific rules feed the generic lifecycle in Decision 0006 and waterfall in Decision 0007.

## 13. Product Limits vs Guarantee Capacity

The usable amount for a transaction is constrained by all applicable gates.

Conceptually:

```
Maximum Usable Principal
= min(
    Participant Available Guarantee Capacity,
    Product Maximum,
    Provider Limit,
    Program Limit,
    Applicable Portfolio Limit
  )
```

The lender may approve an amount up to that maximum.

Badban then issues the guarantee for the final approved principal, preserving Decision 0009 one-to-one matching.

## 14. Direct Lending by Badban

If Badban Direct Lending is enabled, Badban itself appears in the Credit Provider Registry and uses the same Credit Product model.

Direct-lending products must additionally satisfy:

- available direct-lending liquidity;
- direct-credit risk policy;
- applicable legal/regulatory requirements;
- direct-loan accounting and servicing requirements.

External-lender product rules must not be hard-coded into direct-lending products.

## 15. Immutable Terms Snapshot

At guarantee issuance / credit activation, Badban must preserve an immutable snapshot of at least:

- provider;
- product;
- principal;
- guarantee amount;
- currency;
- tenor;
- repayment structure;
- pricing/fees;
- grace rules;
- guarantee exposure mode;
- early repayment rules;
- delinquency/claim rules;
- all relevant policy versions.

Later product configuration changes apply prospectively and must not silently change an active obligation.

## 16. Non-Negotiable Controls

1. No unregistered provider/product may create a guaranteed obligation.
2. External principal must equal issued Badban guarantee amount.
3. Product parameters must be explicit; missing terms are not guessed.
4. Lender-side principal increases require Badban re-approval.
5. Existing obligations keep their captured terms unless validly amended.
6. No guarantee release solely because the scheduled maturity date passed.
7. Settlement, repayment, delinquency, and claim data require authoritative lender evidence.
8. Product rules are configuration/policy, not hard-coded bank-specific business logic.
9. Provider/product suspension blocks new exposure but does not erase existing obligations.
10. All material product changes are versioned and auditable.

## Parameters Deliberately Not Fixed Here

This decision does not set universal production values for:

- loan amount;
- tenor;
- installment frequency;
- pricing/rates;
- fees;
- grace periods;
- delinquency thresholds;
- early repayment charges;
- top-up limits.

Those values belong to approved provider/product configurations.

## Consequences

1. Badban can connect many banks and funds without redesigning the core model.
2. One lender can expose multiple distinct products.
3. The same guarantee engine supports Qard-al-Hasan, conventional bank products, and future direct lending while preserving provider-specific terms.
4. Product changes are governed through versioned configuration.
5. The one-to-one relationship between external principal and guarantee remains a core invariant.

## Follow-up

If Accepted, the next Business decisions should define:

1. Return Allocation Policy;
2. Participant Exit and Entitlement Rules;
3. Direct Lending Liquidity Model, if enabled;
4. Legal / regulated operating structure;
5. Pilot scope and product configuration.
