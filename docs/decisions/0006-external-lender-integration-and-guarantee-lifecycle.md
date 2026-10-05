# Decision 0006 — External Lender Integration and Guarantee Lifecycle

- **Status:** Accepted
- **Date:** 2026-10-05
- **Scope:** Business / Product / Guarantee Operations / External Lender Integration
- **Dependencies:** Decision 0001 — Configurable Asset Input; Decision 0003 — Asset Position Ownership by Funding Source; Decision 0005 — Hybrid Credit Delivery Model

## Problem

Decision 0005 establishes external banks, Qard-al-Hasan funds, and other approved lenders as the preferred credit-delivery channel.

The business model now needs an explicit lifecycle for how Badban:

- exposes guarantee capacity;
- reserves backing;
- issues a guarantee;
- synchronizes with the lender;
- monitors outstanding exposure;
- handles delinquency and claims;
- releases backing after settlement.

Without a common lifecycle, each lender integration could create incompatible rules, double-use backing, or release collateral before the underlying debt is actually closed.

## Decision

Badban shall use one generic **Guarantee Lifecycle** across all external lenders.

Provider-specific contracts and products may configure the rules, but they must map into the same Badban lifecycle and state model.

## 1. Credit Provider Registry

Every external lender must be registered before it can receive Badban backing.

A provider record must define, at minimum:

- provider identity and legal role;
- active / suspended / terminated status;
- supported credit products;
- supported participant segments;
- integration mode;
- guarantee acceptance rules;
- maximum guarantee limits;
- reporting obligations;
- delinquency / claim rules;
- settlement and reconciliation rules;
- SLA / operational contacts;
- effective policy version.

No provider may use Badban guarantee capacity unless it is active under an approved provider policy.

## 2. Credit Product Registry

A lender may expose one or more approved credit products.

Each product must explicitly define:

- lender of record;
- currency;
- minimum and maximum principal;
- tenor range;
- repayment structure;
- permitted pricing / fee structure;
- borrower eligibility;
- required guarantee coverage;
- whether guarantee exposure is fixed or declining;
- delinquency thresholds;
- claim eligibility;
- early-repayment treatment;
- release conditions;
- effective dates and version.

Badban must not infer these rules from lender name or implementation code.

## 3. Guarantee Capacity

Badban calculates a participant's backing-based capacity from eligible Asset Positions under approved valuation and risk policies.

This capacity is not itself a guarantee.

Conceptually:

```
Eligible Asset Positions
        ↓
Valuation + Haircut + Risk Rules
        ↓
Available Backing Capacity
```

A lender request may consume only capacity that is currently available and not already reserved or encumbered.

## 4. Guarantee Lifecycle

The generic lifecycle is:

```
AVAILABLE CAPACITY
      ↓
REQUESTED
      ↓
RESERVED
      ↓
ISSUED
      ↓
ACTIVE
      ├─ RELEASED / CLOSED
      └─ DELINQUENT
             ↓
        CLAIM_PENDING
             ↓
        CLAIM_APPROVED / CLAIM_REJECTED
             ↓
        ENFORCEMENT / SETTLEMENT
             ↓
            CLOSED
```

Cancellation and expiry may occur before activation where policy permits.

### REQUESTED

A lender or authorized Badban flow asks for guarantee coverage for a specific participant, product, amount, and proposed credit transaction.

No backing is yet committed unless the request is simultaneously accepted into reservation.

### RESERVED

Badban has temporarily reserved specific guarantee capacity.

Rules:

- the reservation must reduce available capacity immediately;
- the same backing cannot be reserved twice beyond permitted limits;
- the reservation has an expiry time or explicit cancellation condition;
- reserved capacity is not yet an active guarantee exposure.

### ISSUED

Badban has approved and issued a guarantee commitment under a specific, immutable terms snapshot.

The snapshot must preserve:

- participant;
- lender;
- product;
- approved credit amount;
- guarantee amount / coverage;
- asset positions or backing pool used;
- valuation reference;
- policy versions;
- issuance timestamp;
- expiry / activation conditions.

### ACTIVE

The lender confirms that the underlying loan / credit has become active under the agreed conditions, normally after disbursement or another contractually defined activation event.

At this point:

- guarantee exposure is live;
- backing is encumbered;
- exposure monitoring begins;
- release is prohibited until closure conditions are satisfied.

### DELINQUENT

The lender reports delinquency according to the approved product definition.

Delinquency does not automatically mean Badban pays a claim.

The guarantee remains controlled under the claim policy.

### CLAIM_PENDING

The lender submits a guarantee claim with required evidence.

Badban must reconcile:

- lender identity;
- underlying loan;
- outstanding balance;
- guarantee status;
- claim eligibility;
- prior payments;
- permitted claim amount;
- required collection / cure steps.

A claim must not be accepted solely because the lender reports default.

### CLAIM_APPROVED / CLAIM_REJECTED

Badban makes the contractual guarantee decision under the applicable policy snapshot.

An approved claim creates a settlement / enforcement obligation.

A rejected claim must preserve the reason and supporting evidence.

### ENFORCEMENT / SETTLEMENT

Where contractually permitted, Badban may:

- pay an approved guarantee claim from the applicable reserve or settlement source;
- enforce or liquidate backing;
- net proceeds against the secured exposure;
- handle surplus or shortfall under the Asset Position ownership policy.

The exact default waterfall must be defined in a separate accepted decision.

### RELEASED / CLOSED

Backing may be released only when Badban has authoritative confirmation that all release conditions are satisfied.

At minimum this normally requires:

- underlying exposure is fully settled or otherwise validly closed;
- no valid claim is pending;
- no unresolved reconciliation exists;
- applicable fees / adjustments permitted by policy are finalized;
- release is consistent with the Asset Position ownership policy.

## 5. Exposure Model

Badban must maintain a distinct guarantee exposure record for every guaranteed credit obligation.

At all times it must know:

- lender of record;
- external loan / facility identifier;
- original principal;
- current outstanding balance;
- guarantee coverage amount;
- guarantee exposure amount;
- guarantee status;
- delinquency state;
- claim state;
- backing positions and encumbered value;
- latest lender state timestamp;
- latest Badban reconciliation timestamp.

## 6. Fixed vs Declining Guarantee

The generic model must support both:

### Fixed Guarantee

The guarantee amount remains fixed until contractually released or adjusted.

### Declining Guarantee

Guarantee exposure decreases as eligible principal is repaid.

The provider/product policy decides which mode applies.

Badban must not reduce encumbrance merely because time passed; reduction requires authoritative repayment or settlement evidence.

## 7. Integration Modes

The business model must support multiple integration modes without changing the guarantee domain:

- API integration;
- secure batch/file exchange;
- approved operational portal;
- controlled manual process for pilot or exception cases.

The integration method is operational. The guarantee state and controls remain the same.

## 8. Source of Truth Rule

Badban is the source of truth for:

- backing capacity;
- guarantee reservation;
- guarantee issuance;
- guarantee exposure;
- backing encumbrance;
- guarantee claim decision;
- backing release / enforcement state.

The lender is the source of truth for:

- its credit decision;
- lender-of-record loan terms;
- disbursement state;
- installment receipts;
- its own delinquency servicing;
- lender-side outstanding balance, subject to reconciliation.

Badban must retain a synchronized, auditable copy of lender-reported loan state because guarantee exposure depends on it.

## 9. Safety Controls

1. No guarantee may be issued above available approved capacity.
2. Reservation must be atomic from a business perspective: capacity cannot be promised simultaneously to incompatible obligations.
3. Every issued guarantee is tied to immutable policy and terms versions.
4. A lender cannot unilaterally increase Badban guarantee exposure by changing loan terms.
5. Material loan changes require explicit guarantee re-approval where they affect exposure.
6. Release must be based on authoritative closure evidence.
7. Claims require reconciliation and eligibility validation.
8. Suspended providers cannot create new guarantees.
9. Existing guarantees remain governed by their contractual terms unless legally and contractually amended.
10. All state transitions must be auditable.

## 10. Customer Experience

Badban may present a unified journey to the participant even when the lender is external.

However, the customer record must always clearly identify:

- the lender of record;
- the guaranteed amount;
- the backing used;
- current obligation status;
- which party receives repayments;
- how release or claim affects the backing.

## 11. Consequences

1. Bank and fund integrations can vary technically without fragmenting the core product.
2. Badban becomes a reusable guarantee platform rather than a one-off bilateral integration.
3. One participant can potentially use different approved lenders over time, subject to available capacity and policy.
4. Multiple concurrent credit obligations are possible only if total reservation / encumbrance stays within approved limits.
5. Credit-provider-specific rules live in configuration / policy, not in the generic asset domain.
6. Direct lending by Badban can later map to the same exposure lifecycle with Badban itself as the lender of record, while using a different funding flow.

## Follow-up Decisions

If Accepted, the next Business decisions should define:

1. the **Default and Claim Waterfall**;
2. the **Asset-to-Credit / Guarantee Capacity Formula**;
3. the generic **Credit Product Rules** for limits, tenor, repayment, fees, grace periods, renewals, and top-ups.
