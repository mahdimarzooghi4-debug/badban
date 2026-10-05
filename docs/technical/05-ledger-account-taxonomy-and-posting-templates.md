# Badban Ledger Account Taxonomy and Posting Templates

- **Status:** Accepted
- **Date:** 2026-10-05
- **Stage:** Technical
- **Scope:** bounded external-lender pilot
- **Depends on:** Technical Foundation; Relational Data Model; Decision 0015 — Accounting and Financial Sub-Ledger Model

## 1. Objective

Define the stable Badban **product-level financial account taxonomy** and posting templates for the pilot.

This document does **not** define the statutory chart of accounts of the lender, Guarantee Issuer, custodian, Badban legal entity, or any other regulated party.

The Badban product ledger must preserve economic meaning and ownership in a stable form, then map those product accounts to each legal entity's approved statutory accounting codes.

## 2. Ledger Layers

Badban must distinguish three different accounting/control layers.

### Layer A — Monetary Product Ledger

Used when Badban-controlled economic value actually changes.

Examples:

- recognized return;
- reserve allocation;
- livelihood payable;
- future-financial entitlement;
- claim settlement cash;
- recovery cash;
- final residual loss;
- participant/program payable balance.

Entries are double-entry and monetary.

### Layer B — Exposure / Encumbrance Control Ledger

Used for non-cash commitments and restrictions such as:

- guarantee capacity reserved;
- guarantee exposure active;
- collateral encumbered;
- claim amount approved but not yet paid.

These are **control/memorandum records**, not automatically statutory balance-sheet entries.

They may be represented as paired memorandum postings or append-only control events, but must not be confused with real cash movement.

### Layer C — External Mirror Records

Used for external facts owned by another legal entity:

- external lender loan principal;
- lender outstanding balance;
- external custodian position;
- legal guarantee instrument;
- external collateral registry state.

These are not Badban monetary ledger balances merely because they are stored in Badban.

## 3. Core Product Account Classes

The product taxonomy shall use stable account classes independent of each legal entity's statutory chart.

### A. CONTROLLED_ASSET

Debit-normal economic resources controlled by the responsible legal entity.

Examples:

- settlement cash;
- program cash;
- reserve cash;
- recovery cash;
- receivable/control balance pending recovery.

### B. OWNER_OR_ENTITLEMENT_BALANCE

Credit-normal amounts economically attributable to an owner, participant, program, reserve purpose, or social purpose.

Examples:

- participant payable;
- livelihood payable;
- future-financial entitlement;
- program capital balance;
- guarantee reserve designated balance;
- social-reinvestment balance;
- carry-forward balance.

### C. RETURN_OR_INCOME_CLEARING

Credit-normal recognized return/value pending allocation.

Used as a temporary product-level clearing account before Decision 0012 allocation is posted.

### D. LOSS_OR_COST_CONTROL

Debit-normal recognized economic loss/cost after recovery and allocation are complete.

Examples:

- final guarantee residual loss;
- enforcement cost;
- approved unrecoverable amount.

### E. MEMORANDUM_CONTROL

Non-statutory product-control accounts for exposure/restriction tracking.

Examples:

- guarantee capacity reserved;
- active guarantee exposure;
- backing encumbered;
- approved claim pending settlement.

These accounts must never be included in cash or owner-balance totals.

## 4. Product Account Taxonomy

The following codes are logical product codes, not statutory accounting codes.

### 1000 Series — Controlled Assets

- `1000.SETTLEMENT_CASH_CONTROL`
- `1010.PROGRAM_CASH_CONTROL`
- `1020.GUARANTEE_RESERVE_CASH_CONTROL`
- `1030.RECOVERY_CASH_CONTROL`
- `1040.CLAIM_SETTLEMENT_PENDING_RECOVERY_CONTROL`
- `1050.OTHER_APPROVED_CONTROLLED_ASSET`

### 2000 Series — Owner / Entitlement Balances

- `2000.PARTICIPANT_PAYABLE_BALANCE`
- `2010.LIVELIHOOD_PAYABLE`
- `2020.FUTURE_FINANCIAL_ENTITLEMENT`
- `2030.PROGRAM_CAPITAL_BALANCE`
- `2040.GUARANTEE_RESERVE_DESIGNATED_BALANCE`
- `2050.SOCIAL_REINVESTMENT_BALANCE`
- `2060.RETURN_CARRY_FORWARD_BALANCE`
- `2070.PARTICIPANT_RELEASE_PAYABLE`
- `2080.PROGRAM_RECYCLABLE_BALANCE`

### 3000 Series — Return / Allocation Clearing

- `3000.RECOGNIZED_RETURN_CLEARING`
- `3010.RETURN_ALLOCATION_CLEARING`
- `3020.CAPITAL_GROWTH_CLEARING`

### 4000 Series — Loss / Cost Control

- `4000.GUARANTEE_FINAL_RESIDUAL_LOSS`
- `4010.ENFORCEMENT_COST`
- `4020.APPROVED_FINANCIAL_ADJUSTMENT_LOSS`

### 9000 Series — Memorandum / Control

- `9000.GUARANTEE_CAPACITY_RESERVED_MEMO`
- `9010.ACTIVE_GUARANTEE_EXPOSURE_MEMO`
- `9020.BACKING_ENCUMBERED_MEMO`
- `9030.CLAIM_APPROVED_PENDING_SETTLEMENT_MEMO`
- `9040.CLAIM_SETTLED_RECOVERY_OPEN_MEMO`
- `9050.EXTERNAL_LOAN_PRINCIPAL_MIRROR_MEMO`
- `9060.EXTERNAL_LOAN_OUTSTANDING_MIRROR_MEMO`

The 9000 series is excluded from statutory financial totals unless the responsible legal entity's approved accounting policy explicitly maps a control item to a statutory account.

## 5. Account Dimensions

Every monetary posting must include enough dimensions to answer:

- which legal entity owns/controls the posting;
- which economic owner is affected;
- which participant/program is affected;
- which Asset Position is related;
- which GuaranteeCase is related;
- which Claim/RecoveryCase is related;
- which provider/product is related;
- which reserve type is affected;
- which currency applies;
- which policy version applies.

Required dimensions should be nullable only when truly not applicable.

## 6. Posting Rule

For every POSTED monetary journal:

```
SUM(Debit) = SUM(Credit)
```

No business workflow may update a balance directly.

If a posting template cannot balance, the business transaction fails.

## 7. Reservation Posting Template

### Business event

Guarantee capacity moves from available to RESERVED.

### Monetary ledger

**No monetary posting by default.**

Reason:

No real cash or recognized economic ownership changes merely because capacity is reserved.

### Control ledger

Record:

```
Guarantee Capacity Reserved +X
Backing Reserved +X
```

with links to:

- GuaranteeCase;
- BackingAllocation;
- Asset Position;
- valuation observation;
- policy pack.

This may be represented as memorandum/control postings or append-only control events.

### Hard rule

Reservation must never create revenue, expense, cash, receivable, or payable.

## 8. Guarantee Issuance Posting Template

### Business event

Legal Guarantee Issuer issues guarantee instrument.

### Monetary ledger

**No monetary posting by default.**

### Control ledger

Move control state:

```
Reserved Guarantee Capacity
→ Issued Guarantee Commitment
```

No statutory liability classification is assumed by Badban Core.

That classification belongs to the Guarantee Issuer's approved accounting policy.

## 9. Guaranteed Loan Activation Template

### Preconditions

- issued guarantee exists;
- lender disbursement confirmed;
- external loan principal equals issued guarantee amount;
- backing reservation is valid.

### Monetary ledger

For Badban Core:

**No loan receivable posting.**

Reason:

The external lender is lender of record.

Badban must not post:

```
Dr Loan Receivable
Cr Cash
```

for an external lender loan.

### Control ledger

Move:

```
Guarantee Reserved
→ Active Guarantee Exposure

Backing Reserved
→ Backing Encumbered
```

Create/update external loan mirror:

```
Original External Principal = Issued Guarantee Amount
```

## 10. External Lender Repayment Template

### Business event

Authoritative repayment received by lender.

### Monetary ledger

No Badban monetary cash posting unless Badban itself is a settlement intermediary under an approved structure.

### External mirror

Reduce lender-reported outstanding principal once.

### Declining guarantee control effect

If product mode is DECLINING:

```
Active Guarantee Exposure -Δ
Backing Encumbered -Δ
Backing Available +Δ
```

according to captured product/policy rules.

### Fixed guarantee control effect

No exposure release merely because an installment was paid unless explicit contract/policy permits it.

## 11. Recognized Return Template

This template applies only when return has been validly recognized under the responsible legal entity's approved accounting/economic policy.

### Example — actual cash return received

```
Dr 1000/1010 Controlled Cash            X
Cr 3000 Recognized Return Clearing       X
```

Dimensions must preserve whether the return belongs economically to:

- participant-owned position;
- program-attributed position;
- other approved ownership type.

### Example — recognized non-cash receivable

If accounting policy permits a recognized receivable:

```
Dr Approved Receivable-Control Account   X
Cr 3000 Recognized Return Clearing       X
```

Badban must not invent non-cash recognition when policy does not permit it.

## 12. Return Allocation Template

For eligible net return X:

```
Dr 3000 Recognized Return Clearing       X

Cr 2040 Guarantee Reserve Designated      R
Cr 2010 Livelihood Payable                M
Cr 2020 Future Financial Entitlement      F
Cr 3020 Capital Growth Clearing           G
Cr 2050 Social Reinvestment Balance       S
Cr 2060 Return Carry Forward              C
```

Invariant:

```
X = R + M + F + G + S + C
```

No residual may remain unexplained.

## 13. Capital Growth Posting Template

Capital growth must be posted according to ownership/funding type.

### Participant-Owned position

Conceptually:

```
Dr 3020 Capital Growth Clearing          G
Cr 2000 Participant Payable/Capital      G
```

or into a dedicated participant capitalized-balance account mapped to the related Asset Position.

### Program-Attributed position

Conceptually:

```
Dr 3020 Capital Growth Clearing          G
Cr 2030 Program Capital Balance          G
```

If capitalization purchases/increases an actual Asset Position, a separate asset acquisition/quantity event and settlement evidence are required.

Ledger allocation alone does not create asset quantity.

## 14. Livelihood Payment Template

When livelihood amount becomes payable:

Allocation posting already creates:

```
Cr 2010 Livelihood Payable
```

When actual payment occurs:

```
Dr 2010 Livelihood Payable               X
Cr 1000/1010 Controlled Cash             X
```

External settlement reference is mandatory.

A journal posting without settlement evidence must remain in a pending workflow and must not be shown as externally paid.

## 15. Future Financial Payment Template

When a vested future-financial entitlement is paid:

```
Dr 2020 Future Financial Entitlement     X
Cr Controlled Cash                       X
```

The entitlement sub-ledger must be reduced in the same business transaction.

Payment cannot exceed vested payable balance.

## 16. Reserve Funding / Reclassification Template

When already-controlled program cash is formally designated as guarantee reserve:

```
Dr 2030 Program Capital/Available Balance      X
Cr 2040 Guarantee Reserve Designated Balance   X
```

If reserve cash is physically moved to a segregated bank account, a second asset-side reclassification may occur:

```
Dr 1020 Guarantee Reserve Cash Control         X
Cr 1010 Program Cash Control                   X
```

These two events are conceptually distinct:

1. economic designation;
2. actual bank/cash movement.

They may occur together only when external settlement evidence confirms the transfer.

## 17. Claim Approval Template

### Business event

Claim is approved, but not yet paid.

### Monetary ledger

No final loss posting yet.

Depending on approved accounting policy, the responsible legal entity may need statutory recognition, but Badban Core does not guess it.

### Control ledger

Record:

```
Approved Claim Pending Settlement +X
```

linked to GuaranteeCase and GuaranteeClaim.

## 18. Claim Settlement Template

When approved claim payment is externally confirmed from reserve cash:

```
Dr 1040 Claim Settlement Pending Recovery Control    X
Cr 1020 Guarantee Reserve Cash Control                X
```

Interpretation:

- reserve cash left the controlled reserve;
- the economic outcome is not yet classified as final loss;
- recovery/enforcement remains open.

Control ledger moves:

```
Claim Approved Pending Settlement
→ Claim Settled / Recovery Open
```

## 19. Recovery Cash Receipt Template

When recovery cash is actually received:

```
Dr 1030 Recovery Cash Control                       Y
Cr 1040 Claim Settlement Pending Recovery Control   Y
```

Then allocate the recovered cash to its approved destination.

If policy requires reimbursement of reserve:

```
Dr 2040 / appropriate recovery-allocation source    Y
Cr 2040 Guarantee Reserve Designated Balance         Y
```

and, where the cash itself is transferred back into the reserve bank account:

```
Dr 1020 Guarantee Reserve Cash Control               Y
Cr 1030 Recovery Cash Control                        Y
```

The exact combination depends on whether designation and actual cash transfer are separate events.

## 20. Collateral Realization Template

Collateral realization requires two layers.

### Asset quantity / custody layer

Record authoritative decrease/realization of the encumbered Asset Position.

### Cash/economic layer

If proceeds enter a controlled settlement account:

```
Dr 1030 Recovery Cash Control                       X
Cr 1040 Claim Settlement Pending Recovery Control   X
```

up to the amount attributed to recovery of the settled claim.

Any excess proceeds must be posted to the rightful owner balance:

Participant-owned surplus:

```
Cr 2000 / 2070 Participant Balance / Release Payable
```

Program-attributed surplus:

```
Cr 2030 / 2080 Program Capital / Recyclable Balance
```

The system must not treat surplus as Badban corporate income by default.

## 21. Final Residual Loss Template

After all approved recovery activity is complete, unresolved claim settlement amount becomes final residual loss.

If remaining pending recovery control = L:

```
Dr 4000 Guarantee Final Residual Loss               L
Cr 1040 Claim Settlement Pending Recovery Control   L
```

At this point:

```
Claim Settlement Outflow
- Total Recovery
= Final Residual Loss
```

subject to approved costs and recovery allocation rules.

## 22. Enforcement Cost Template

If a valid enforcement cost is paid from controlled cash:

```
Dr 4010 Enforcement Cost                            X
Cr Controlled Cash                                 X
```

If the cost is contractually recoverable from proceeds, the RecoveryCase allocation logic must separately track and settle that entitlement.

## 23. Participant-Owned Asset Release Template

Releasing participant-owned collateral after obligations close has two distinct cases.

### Case A — asset remains in external custody and restriction is lifted

No monetary journal.

Control/asset layer:

```
Backing Encumbered → Released
Asset Position Restriction → Released
```

### Case B — Badban-controlled cash/value becomes payable to participant

```
Dr relevant Participant Economic Balance           X
Cr 2070 Participant Release Payable                 X
```

Then on actual external payment:

```
Dr 2070 Participant Release Payable                 X
Cr Controlled Cash                                 X
```

Do not post a payment merely because the asset becomes releasable.

## 24. Program-Attributed Capital Recycling Template

When a participant exits and program-attributed capital becomes recyclable:

```
Dr current Program Attribution Balance             X
Cr 2080 Program Recyclable Balance                 X
```

When reassigned to a new participant episode:

```
Dr 2080 Program Recyclable Balance                 X
Cr 2030 Program Capital Balance / New Attribution  X
```

No participant-owned balance is involved unless a separately vested entitlement exists.

## 25. Social Reinvestment Template

When return allocation creates social reinvestment balance:

```
Cr 2050 Social Reinvestment Balance
```

When governance later deploys that balance into a permitted program purpose:

```
Dr 2050 Social Reinvestment Balance                X
Cr appropriate controlled cash / program source    X
```

The destination must identify the receiving program/economic owner.

It must not be silently reclassified as Badban operating revenue.

## 26. Reversal Template

Every posted monetary correction uses a linked reversal.

If original entry was:

```
Dr A  X
Cr B  X
```

the reversal is:

```
Dr B  X
Cr A  X
```

with:

- `reversal_of_entry_id`;
- correction reason;
- actor;
- approval;
- correlation/causation reference.

A corrected replacement entry, if needed, is posted separately.

## 27. No-Posting Events

The following business events do **not** automatically create monetary journal entries:

- valuation observation;
- guarantee capacity calculation;
- reservation;
- legal guarantee issuance;
- external lender credit approval;
- external loan disbursement itself;
- repayment at external lender;
- delinquency state;
- claim submission;
- claim rejection;
- release of an external collateral restriction.

They may create:

- audit events;
- memorandum/control events;
- external mirror updates;
- reconciliation items.

A monetary journal is created only when Badban-controlled economic value or a recognized owner/entitlement balance changes.

## 28. Posting Engine Contract

Every posting template invocation must provide:

- business event type;
- business event ID;
- legal entity;
- currency;
- policy version;
- economic owner dimensions;
- participant/program dimensions where applicable;
- related GuaranteeCase/Claim/Asset Position;
- idempotency key;
- effective timestamp;
- actor/system;
- evidence/settlement reference where required.

The posting engine must:

1. resolve template version;
2. validate required dimensions;
3. build postings;
4. verify debits = credits;
5. verify account/dimension compatibility;
6. verify idempotency;
7. post atomically;
8. emit audit/outbox event.

## 29. Template Versioning

Posting templates are versioned.

Historical entries retain:

- template code;
- template version;
- policy version;
- legal-entity account mapping version.

Changing a mapping or posting template never rewrites previously posted journals.

## 30. Account Mapping

Each responsible legal entity may map product accounts differently.

Example:

```
Badban Product Account
        ↓
Legal Entity Account Mapping
        ↓
Entity Statutory Chart Code
```

The mapping table must support:

- effective date range;
- mapping version;
- legal entity;
- product account code;
- statutory/external account code.

No mapping means no statutory export for that account; the system must fail or flag configuration rather than guess.

## 31. Trial Balance and Integrity Checks

The product ledger must support at least:

### Journal balance check

For every POSTED entry:

```
Debits = Credits
```

### Account balance rebuild

All balances must be reproducible from journal postings.

### Owner-balance reconciliation

Participant/program/entitlement balances must reconcile to sub-ledger projections.

### Reserve reconciliation

Reserve designated balance and reserve cash/control balance must be separately reconcilable.

### Claim reconciliation

```
Total Claim Settlement
=
Recovered Amount
+ Final Residual Loss
+ Open Pending Recovery
```

subject to approved enforcement costs/allocation treatment.

## 32. Hard Ledger Invariants

1. No external lender loan is posted as a Badban corporate receivable.
2. No guarantee reservation creates cash or revenue.
3. No valuation creates income merely because market value increased.
4. Participant collateral is not a general reserve account.
5. Claim payment is not automatically final loss.
6. Participant/program/social surplus ownership is explicit.
7. Return allocation balances completely.
8. No posted entry is edited.
9. Every correction is traceable through reversal/adjustment.
10. Every monetary posting belongs to exactly one legal-entity context.
11. Product accounts never silently imply statutory accounting classification.
12. External settlement evidence is required before a cash movement is marked completed.

## 33. Read Models Derived from Ledger

Derived projections should include:

- participant payable balance;
- livelihood payable;
- future-financial balance;
- program capital balance;
- recyclable program balance;
- reserve designated balance;
- reserve cash balance;
- claim settlement pending recovery;
- recovered amount;
- final guarantee loss.

These projections are rebuildable from posted journal history.

## 34. Technical Follow-up

The next Technical contracts should define:

1. Policy/versioning runtime model;
2. API command/query contracts;
3. domain/integration event contracts;
4. provider adapter contracts;
5. reconciliation engine contract.
