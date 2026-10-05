# Decision 0016 — Pilot Boundary and Initial Policy-Pack Governance

- **Status:** Proposed
- **Date:** 2026-10-05
- **Scope:** Business / Pilot / Product Boundary / Release Governance
- **Dependencies:** Decision 0005 — Hybrid Credit Delivery Model; Decision 0008 — Policy-Driven Asset-to-Guarantee Capacity Formula; Decision 0009 — One-to-One External Loan and Badban Guarantee; Decision 0010 — Risk Appetite and Guarantee Reserve Framework; Decision 0011 — Configurable Credit Product Rules; Decision 0013 — Participant Exit and Entitlement Rules; Decision 0014 — Regulated Operating Structure and Legal-Role Separation; Decision 0015 — Accounting and Financial Sub-Ledger Model

## Problem

Badban's core business model is now substantially defined.

Before Technical architecture begins, the first production-oriented boundary must be explicit so the team does not attempt to implement every future capability at once.

The pilot must validate the complete Badban value chain while minimizing regulatory, accounting, operational, and integration complexity.

It must also avoid inventing unapproved numeric financial parameters.

## Proposed Decision

Badban shall begin with a **bounded external-lender pilot**.

The pilot is designed to prove one complete and auditable chain:

```
Participant
→ Approved Asset Position
→ Valuation
→ Guarantee Capacity
→ Risk Gate
→ Guarantee Issuance
→ External Lender Loan
→ Disbursement Confirmation
→ Repayment Monitoring
→ Guarantee Reduction / Release
→ Exit / Reconciliation
```

The pilot does **not** need to activate every future Badban capability.

## 1. Pilot Credit Channel

The initial pilot shall use:

```
External Lender + Badban Guarantee
```

not Badban Direct Lending.

Therefore:

```
Badban Direct Lending = OUT OF PILOT SCOPE
```

until the legal, regulatory, capital, liquidity, accounting, and operational gates are separately approved.

Decision 0004 remains a future-scope direct-lending decision and does not block the external-lender pilot.

## 2. External Lender Boundary

The pilot should begin with **one approved lender integration**.

The selected lender may be:

- a bank;
- an authorized Qard-al-Hasan provider;
- another legally authorized credit provider.

The exact lender is not fixed by this decision.

Activation requires:

- verified legal status;
- approved contract;
- accepted Badban guarantee instrument;
- defined data exchange;
- defined disbursement/repayment reporting;
- defined delinquency/claim rules;
- operational test completion.

## 3. Guarantee Issuer Boundary

The pilot shall use **one legally validated Guarantee Issuer**.

This may be:

- an approved licensed guarantee fund/vehicle;
- another legally permitted guarantee structure.

The pilot must not proceed on the assumption that Badban Core itself is the legal guarantor unless the legal basis is explicitly validated.

## 4. Asset-Type Boundary

The pilot shall activate **one Asset Type** for production use.

Gold is the default candidate because it is already contemplated by the original Badban concept and Decision 0001 treats it as an initial supported Asset Type.

However:

```
Gold Candidate ≠ Gold Hard-Coded Core
```

The selected pilot Asset Type must pass all of the following before activation:

- legal ownership model approved;
- lawful custody/control path approved;
- authoritative valuation source approved;
- valuation freshness rule approved;
- Advance Rate approved;
- pledge/encumbrance method approved;
- enforcement/release path approved;
- external registry requirement resolved;
- reconciliation source available.

If gold fails those gates, another approved Asset Type may be selected without redesigning the core model.

## 5. Ownership/Funding Boundary

The pilot should start with a clearly defined ownership/funding policy.

At minimum, the pilot must explicitly state whether each position is:

- PARTICIPANT_OWNED; or
- PROGRAM_ATTRIBUTED.

The pilot may support both only if the legal/custody/accounting flows for both are validated.

For risk reduction, the first operational cohort may be limited to one ownership/funding mode.

No pilot position may have ambiguous ownership.

## 6. Participant Cohort

The pilot shall use a **closed, explicitly enrolled cohort**.

The cohort definition must include:

- sponsoring/supporting program;
- eligibility source;
- enrollment authority;
- participant consent/disclosure;
- geographic/operational boundary where relevant;
- inclusion/exclusion rules;
- exit rules.

The exact participant count is not fixed by this decision.

The cohort must be small enough for controlled reconciliation and exception handling, but large enough to exercise the complete lifecycle.

## 7. One-to-One Loan Rule

Decision 0009 remains a hard pilot invariant:

```
External Loan Principal = Issued Badban Guarantee Amount
```

A pilot transaction must not activate if the lender disburses a principal different from the issued guarantee amount.

This mismatch is a hard exception.

## 8. Pilot Product Count

The pilot should begin with **one external credit product**.

That product must define:

- lender;
- principal minimum/maximum;
- tenor;
- repayment schedule;
- fees/pricing;
- grace rules;
- fixed/declining guarantee mode;
- early repayment;
- delinquency;
- claim rules;
- top-up/renewal policy.

Additional products are added only after the initial product has completed controlled operational validation.

## 9. Numeric Financial Parameters

This decision deliberately does **not** invent production values.

Before pilot activation, governance must approve a versioned **Pilot Policy Pack** containing the actual numbers for:

- Asset Type Advance Rate / Haircut;
- maximum valuation age;
- participant guarantee limit;
- product minimum/maximum;
- provider limit;
- portfolio exposure limit;
- concentration limits;
- reserve requirement;
- reserve warning/hard thresholds;
- guarantee reservation validity;
- tenor;
- grace period;
- delinquency threshold;
- claim timing;
- return-allocation percentages, if return allocation is active in the pilot.

No default numeric value may be supplied by the software when the Pilot Policy Pack is incomplete.

## 10. Pilot Policy Pack Status

The Pilot Policy Pack shall have a lifecycle:

```
DRAFT
→ REVIEWED
→ APPROVED
→ ACTIVE
→ SUPERSEDED / RETIRED
```

Only an ACTIVE policy pack can authorize real pilot transactions.

Each transaction must capture the exact policy-pack version used.

## 11. Initial Functional Scope — In

The pilot must support the following end-to-end capabilities:

- participant/program enrollment;
- legal-entity/provider registry;
- Asset Type Registry;
- Asset Position creation;
- ownership/funding classification;
- custody/reference evidence;
- valuation;
- guarantee-capacity calculation;
- portfolio risk gate;
- guarantee reservation;
- legal guarantee issuance synchronization;
- lender approval synchronization;
- one-to-one disbursement verification;
- external-loan mirror;
- repayment synchronization;
- guarantee exposure reduction/release;
- collateral release;
- append-only financial sub-ledger;
- provider reconciliation;
- participant statement;
- risk/operations dashboard;
- audit trail;
- participant exit/reconciliation.

## 12. Initial Functional Scope — Out

The following are not required for first pilot activation unless separately approved:

- Badban Direct Lending;
- multiple simultaneous lenders;
- multiple Asset Types;
- multi-currency;
- automated cross-collateralization;
- complex securitization;
- secondary-market transfer;
- AI credit decisioning;
- opaque automated participant profiling;
- unrestricted participant-to-participant asset transfer;
- automatic enforcement without authorized review;
- generalized open-market consumer lending.

Excluding these from the pilot does not prohibit future versions.

## 13. Manual-Control Allowance

The pilot may use controlled manual operations for a limited set of externally constrained steps where API integration is unavailable.

Examples may include:

- provider confirmation;
- legal guarantee issuance confirmation;
- collateral registry confirmation;
- exceptional reconciliation.

Manual operation is allowed only when:

- actor is identified;
- evidence is attached/referenced;
- maker/checker control applies where required;
- action is timestamped;
- state transition remains auditable.

A manual workaround must not bypass a risk/legal gate.

## 14. Required Reconciliation Quality

Before a pilot transaction is considered operationally complete:

- internal Asset Position must reconcile to custody/registry evidence;
- guarantee state must reconcile to Guarantee Issuer evidence;
- external loan mirror must reconcile to lender evidence;
- external cash movement must reconcile to settlement evidence;
- collateral release must reconcile to legal/custody evidence.

Material unresolved mismatch blocks final closure.

## 15. Pilot Success Criteria

Pilot success must be measured across five dimensions.

### A. Financial Integrity

- no double use of backing;
- no unexplained ledger imbalance;
- no unreconciled participant ownership;
- no guarantee/loan principal mismatch;
- all claim/recovery events traceable if exercised.

### B. Operational Integrity

- all lifecycle states reachable through approved transitions;
- exception handling works;
- manual actions remain auditable;
- provider reconciliation is repeatable.

### C. Risk Integrity

- participant capacity gates work;
- portfolio risk gates work;
- reserve gates work;
- stale valuation blocks new capacity;
- provider/license suspension blocks new exposure.

### D. Participant Integrity

- participant can understand:
  - owned vs program-attributed assets;
  - guarantee amount;
  - lender identity;
  - outstanding obligation;
  - restricted/releasable backing;
  - allocated return/entitlement where applicable.

### E. Legal/Regulatory Integrity

- every regulated action maps to a validated legal entity;
- selected guarantee instrument is legally usable for the selected product;
- selected lender is authorized;
- selected custody/encumbrance path is valid;
- required disclosures/consents are implemented.

## 16. Hard Pilot Stop Conditions

New pilot transactions must stop if any of the following occurs:

- legal authorization becomes invalid or unclear;
- lender/guarantor/custodian status becomes suspended/expired;
- portfolio risk state is RED;
- required reserve falls below hard minimum;
- authoritative valuation becomes unavailable beyond policy tolerance;
- critical reconciliation mismatch remains unresolved;
- guarantee/loan one-to-one invariant fails;
- accounting ledger loses balance/integrity;
- external collateral registration is required but cannot be confirmed.

Existing obligations continue to be serviced under their valid terms.

## 17. Pilot Data and Evidence

The pilot must retain enough structured evidence to support the next improvement cycle.

At minimum:

- onboarding outcomes;
- valuation history;
- capacity calculations;
- guarantee issuance time;
- lender approval/disbursement time;
- repayment synchronization quality;
- reconciliation exceptions;
- delinquency/claim data if any;
- reserve utilization;
- participant support queries;
- operational exceptions;
- exit/release timing.

No pilot metric may rely only on anecdotal observation when a system event can be recorded.

## 18. No Automatic Scale-Up

Passing pilot metrics does not automatically expand Badban to:

- more participants;
- more Asset Types;
- more lenders;
- higher limits;
- direct lending.

Scale-up requires explicit Release Approval / governance approval and a new or superseding policy pack.

## 19. Pilot-to-Technical Gate

Technical architecture may begin after this decision is Accepted because the business domain and pilot boundary will then be sufficiently constrained.

However, real-money pilot activation still requires:

- approved Pilot Policy Pack;
- named/validated lender;
- named/validated Guarantee Issuer;
- named/validated custody/asset path;
- accounting mappings;
- legal sign-off on the chosen pilot structure;
- Stage/QA/Release gates under the parent development process.

## Consequences

1. Badban Technical architecture can focus on the real first-use case instead of all future channels.
2. Direct lending remains strategically possible but is not a pilot dependency.
3. One lender, one product, one Asset Type, and one guarantee path create a controlled first operating model.
4. Numeric risk/product values remain governance decisions rather than software assumptions.
5. Pilot evidence can drive later policy refinement and scale-up.

## Follow-up

If Accepted, the next step is the **Business-Stage Completion Review**.

That review should:

1. verify all Accepted decisions are internally consistent;
2. identify any remaining Proposed decisions that are outside pilot scope or still blocking;
3. produce the Technical-stage input package;
4. formally determine whether Badban may move from Business → Technical.
