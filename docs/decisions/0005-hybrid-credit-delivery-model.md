# Decision 0005 — Hybrid Credit Delivery Model

- **Status:** Accepted
- **Date:** 2026-10-05
- **Scope:** Business / Product / Operating Model / Credit Delivery
- **Dependencies:** Decision 0001 — Configurable Asset Input; Decision 0003 — Asset Position Ownership by Funding Source
- **Supersedes:** Decision 0002 — Unified Asset and Credit Operator

## Decision

Badban shall support a **hybrid credit delivery model**.

The preferred and primary operating pattern is:

1. Badban manages or controls the approved backing asset position;
2. Badban calculates and maintains the eligible backing / guarantee capacity;
3. Badban connects to external lenders such as banks and Qard-al-Hasan funds;
4. the external lender originates and disburses the loan or credit;
5. Badban provides the approved guarantee / collateral backing and monitors the secured exposure.

Badban may also support **direct lending by Badban itself** when the required legal, regulatory, funding, risk, accounting, and operational conditions are satisfied.

Direct lending is therefore an allowed channel, not a mandatory dependency and not the preferred default.

## Core Rule

```
One Backing Engine
      ↓
Multiple Credit Delivery Channels
      ├─ External Bank
      ├─ External Qard-al-Hasan Fund
      ├─ Other Approved Lender
      └─ Badban Direct Lending (optional)
```

The backing and guarantee engine must remain channel-agnostic.

## Channel A — External Lender / Guarantee Model

This is the preferred channel.

Badban responsibilities may include:

- asset intake / administration;
- ownership and custody state;
- valuation and revaluation;
- eligibility and haircut rules;
- calculation of backing / guarantee capacity;
- reservation and encumbrance of backing;
- issuance and lifecycle management of guarantee commitments;
- lender integration;
- exposure monitoring;
- release or enforcement of backing under approved rules;
- reconciliation and reporting.

External lender responsibilities may include, subject to integration and contract:

- borrower credit review;
- loan product selection;
- approval;
- disbursement;
- installment collection;
- delinquency servicing;
- reporting loan state to Badban;
- guarantee claim submission when applicable.

The exact split is lender- and contract-specific and must be represented explicitly rather than assumed.

## Channel B — Badban Direct Lending

Badban may originate and service credit directly.

When this channel is enabled, Badban must additionally manage:

- an approved lending liquidity source;
- loan origination;
- disbursement;
- receivables;
- repayment servicing;
- delinquency;
- loss recognition;
- liquidity and capital risk;
- applicable licensing and regulatory obligations.

Direct lending must reuse the same backing / guarantee-capacity engine used for external lenders where possible.

## Product Architecture Consequences

1. Badban must not hard-code a single lender.
2. The system needs a **Lender / Credit Provider Registry**.
3. Each credit provider may have:
   - supported products;
   - eligibility rules;
   - guarantee requirements;
   - integration protocol;
   - settlement rules;
   - claim process;
   - reporting obligations;
   - service status and limits.
4. A participant may receive credit from an external lender or, where enabled, from Badban.
5. The customer experience may remain unified even when the legal lender is external.
6. Badban must always know:
   - which entity is the lender of record;
   - which asset positions back the obligation;
   - guarantee amount and status;
   - current outstanding balance;
   - repayment / delinquency state;
   - release / claim / enforcement state.
7. Lender-specific product logic must not leak into the generic asset and backing domain unless required by explicit policy.

## Rationale

The external-lender guarantee model preserves Badban's original strength: using managed assets to remove the traditional guarantor barrier while leveraging existing banking and Qard-al-Hasan lending capacity.

At the same time, allowing direct lending keeps the product strategically flexible and avoids creating a permanent architectural limitation if Badban later has the legal and financial ability to lend itself.

## Relationship to Decision 0002

Decision 0002 required a single operating entity to handle both the asset and the loan. That requirement is no longer the target model.

The accepted model is now:

- **preferred:** Badban as backing / guarantee platform connected to external lenders;
- **optional:** Badban as lender itself.

Decision 0002 is therefore superseded by this decision.

## Follow-up

Decision 0004 must be interpreted and revised so that a dedicated lending liquidity pool is required only for the **Badban Direct Lending** channel. External-lender channels use the lender's own approved funding source and do not require Badban to fund the loan principal.
