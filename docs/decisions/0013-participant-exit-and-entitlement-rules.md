# Decision 0013 — Participant Exit and Entitlement Rules

- **Status:** Proposed
- **Date:** 2026-10-05
- **Scope:** Business / Participant Lifecycle / Ownership / Entitlements / Exit
- **Dependencies:** Decision 0003 — Asset Position Ownership by Funding Source; Decision 0006 — External Lender Integration and Guarantee Lifecycle; Decision 0007 — Default, Claim, Recovery, and Loss Waterfall; Decision 0008 — Policy-Driven Asset-to-Guarantee Capacity Formula; Decision 0012 — Policy-Driven Return Allocation

## Problem

Badban must distinguish the end of a participant's support-program membership from the settlement of their financial rights and obligations.

The original proposal states that:

- future-financial support may continue for a transition period after support exit;
- program capital should remain in the social-capital cycle;
- exit rules must preserve the participant's economic rights while also preserving the social-capital cycle.

The evolving Badban model additionally distinguishes participant-owned assets from program-attributed assets.

Therefore exit cannot be implemented as one generic action such as “close participant and return everything” or “return everything to the program.”

## Proposed Decision

Badban shall treat participant exit as a **controlled financial transition**, not as an immediate deletion or blanket asset release.

The system must determine separately:

1. support-program membership status;
2. participant-owned asset rights;
3. program-attributed asset rights;
4. vested future-financial entitlement;
5. outstanding guarantees and loans;
6. pending claims / delinquency / enforcement;
7. posted but unpaid allocations;
8. final releasable, recyclable, or restricted balances.

## 1. Core Rule

```
Program Exit ≠ Financial Closure
```

A participant may exit the support program while financial obligations or entitlements remain active.

The account may therefore remain financially open after support membership ends.

## 2. Exit Lifecycle

Badban should support a generic exit lifecycle:

```
ACTIVE
  ↓
EXIT_ELIGIBLE
  ↓
EXIT_INITIATED
  ↓
FINANCIAL_RECONCILIATION
  ├─ OBLIGATIONS_OPEN
  ├─ TRANSITION_SUPPORT_ACTIVE
  └─ READY_FOR_FINALIZATION
          ↓
FINALIZED
```

Exceptional states may include:

- EXIT_SUSPENDED;
- LEGAL_HOLD;
- DECEASED;
- INCAPACITATED;
- TRANSFER_PENDING.

These states must not silently alter ownership or obligations.

## 3. Participant-Owned Principal

For a **Participant-Owned Asset Position**:

- economic ownership remains with the participant or other legal owner;
- program exit does not transfer the asset to Badban or the social pool;
- if the position is free of valid encumbrances and restrictions, it becomes releasable to the owner;
- if it backs an active guarantee, loan, claim, or enforcement process, it remains restricted until the relevant obligation is validly closed;
- release requires authoritative reconciliation and an auditable release event.

The participant-owned asset must not be recycled into the social-capital pool by default.

## 4. Program-Attributed Principal

For a **Program-Attributed Asset Position**:

- the participant's support relationship may end while the principal remains owned/controlled by the program structure;
- the principal does not become automatically withdrawable by the participant at exit;
- after all participant-linked obligations are resolved, the principal may be returned to or remain in the approved social-capital pool;
- the same capital may later be allocated to another eligible participant under policy;
- any participant entitlement that has vested from the return-allocation process remains separate from the program principal.

This preserves capital recycling without overriding separately defined participant rights.

## 5. Capital-Growth Ownership

Capital-growth allocations inherit the ownership policy of the position to which they were capitalized unless an explicit approved policy states otherwise.

Therefore:

### Participant-Owned Position

Capitalized return added to a participant-owned position is participant-owned unless contract/policy validly defines another treatment.

### Program-Attributed Position

Capitalized return added to a program-attributed position remains program-attributed unless a defined portion explicitly vests to the participant.

Badban must not infer ownership from the label “capital growth” alone.

## 6. Future Financial Entitlement

The **Future Financial Support** bucket created under Decision 0012 must be tracked separately from principal.

At exit, Badban must determine:

- vested amount;
- unvested amount;
- payout schedule;
- transition duration;
- conditions for continuation;
- conditions for suspension or termination;
- expiry, if any;
- beneficiary or successor rules where applicable.

Future-financial support is funded from the allocated future-financial balance or other explicitly approved source.

Program principal is not automatically consumed to fund future support.

## 7. Livelihood Payments at Exit

Ongoing livelihood payments do not automatically continue indefinitely after program exit.

The applicable program policy must define whether they:

- stop at exit;
- taper during transition;
- continue for a fixed period;
- convert into another support form.

The decision must be explicit and versioned.

## 8. Outstanding Guarantee or Loan

A participant cannot obtain full release of backing merely because support membership ended.

If an external or direct loan remains outstanding:

- the lender relationship continues under the loan terms;
- active Badban guarantee exposure remains valid;
- backing remains encumbered as required;
- repayment monitoring continues;
- delinquency/claim/enforcement rules remain applicable;
- final asset release/recycling waits for valid closure.

Support-program exit must not weaken a valid guarantee already issued.

## 9. Pending Guarantee Reservation

If an exit begins while a guarantee is only RESERVED and the loan has not activated, policy must define whether the reservation:

- is cancelled;
- is allowed to complete;
- requires re-approval;
- expires on the normal reservation deadline.

No default assumption may silently activate or cancel it.

## 10. Delinquency, Claim, or Enforcement at Exit

If exit occurs during delinquency, claim, or enforcement:

- the participant record remains financially active for the affected obligation;
- relevant backing stays restricted;
- Decision 0007 waterfall continues;
- surplus and shortfall follow the ownership and guarantee rules;
- exit finalization may proceed only for balances not subject to the active process.

Badban must support **partial financial closure** so unrelated clean positions do not remain blocked without reason.

## 11. Posted but Unpaid Return Allocations

At exit, all posted allocation balances must be reconciled.

The system must distinguish:

- participant-owned payable balance;
- future-financial balance;
- capitalized balance;
- program/social-reinvestment balance;
- reserve allocation;
- unposted/draft allocation.

Only valid posted/vested participant amounts are treated as participant entitlements.

Draft or projected returns are not payable entitlements merely because they appeared in a forecast.

## 12. Exit Statement

Before finalization, Badban must produce an auditable exit statement showing, as applicable:

- participant-owned principal;
- program-attributed principal;
- encumbered backing;
- outstanding guaranteed principal;
- pending claims;
- vested future-financial amount;
- unpaid livelihood amount;
- capital-growth ownership;
- social-reinvestment balance;
- releasable amount;
- recyclable program amount;
- restricted amount;
- unresolved items.

A participant should be able to understand why each amount is released, retained, paid later, or recycled.

## 13. Finalization Conditions

An exit may be marked **FINALIZED** only when:

- support-membership status is closed;
- all ownership classifications are known;
- all participant entitlements are calculated;
- all releasable participant-owned assets are released or scheduled;
- all recyclable program assets are identified;
- active obligations are either closed or explicitly carried forward under a post-exit state;
- unresolved legal/claim holds are recorded;
- a final reconciliation and audit trail exist.

FINALIZED does not necessarily mean every future-financial payment has already been paid. It means the rights and obligations are fully determined and governed.

## 14. Death

Death of a participant must not cause automatic transfer of participant-owned assets to Badban or the program.

The system must:

- freeze unauthorized disposition;
- preserve ownership and obligation records;
- continue valid loan/guarantee handling;
- await the legally/contractually authorized successor or estate process;
- separately handle program-attributed positions under program policy.

Detailed inheritance/succession rules are jurisdiction-specific and require a later legal decision.

## 15. Incapacity

If a participant loses legal or operational capacity:

- ownership does not automatically change;
- authorized representative rules must apply;
- financial restrictions may be imposed to protect the participant;
- active guarantee/loan obligations remain governed by their valid terms.

The exact authority model requires legal implementation.

## 16. Transfer

No participant-owned or program-attributed position may be transferred merely because a participant exits.

Transfer requires:

- an eligible receiving party;
- ownership/policy permission;
- absence or resolution of conflicting encumbrances;
- explicit authorization;
- auditable settlement.

Program capital recycling to a new participant is an allocation action by the program, not a transfer of the former participant's ownership rights.

## 17. Re-entry

A former participant may later re-enter a support program only under a new eligibility decision.

Re-entry must not silently reactivate old:

- allocation profiles;
- guarantees;
- ownership classifications;
- credit products;
- policy versions.

Historical records remain immutable and linked to the new participation episode.

## 18. Non-Negotiable Controls

1. Program exit does not erase financial obligations.
2. Participant-owned principal is not recycled into social capital by default.
3. Program-attributed principal is not automatically withdrawable by the participant.
4. Active backing is not released while valid exposure remains.
5. Future-financial entitlement is separate from principal.
6. Draft/projected return is not a vested entitlement.
7. Capital-growth ownership follows the underlying ownership policy unless explicitly overridden.
8. Exit requires a full reconciliation statement.
9. Death/incapacity does not silently transfer ownership.
10. Historical participation and new re-entry episodes remain distinct and auditable.

## Relationship to the Original Proposal

The original proposal's general exit concept remains valid for **program-attributed social capital**: principal can remain in the Badban cycle and future-financial support can continue during a transition period.

Decision 0003 narrows this rule: it does **not** apply to assets that are participant-owned.

This decision makes that distinction explicit.

## Parameters Deliberately Not Fixed Here

This decision does not define universal values for:

- transition-support duration;
- future-financial payout schedule;
- vesting period;
- livelihood taper period;
- exit eligibility criteria;
- re-entry waiting period.

Those values belong to versioned program policies.

## Consequences

1. Badban can preserve the social-capital recycling model without taking participant-owned assets.
2. Exit becomes auditable rather than a single destructive event.
3. Outstanding loans and guarantees remain safe across program exit.
4. Future-financial support becomes a distinct participant entitlement.
5. Program-attributed capital can be recycled after obligations are resolved.
6. Death, incapacity, transfer, and re-entry can be handled without corrupting ownership history.

## Follow-up

If Accepted, the next Business decisions should define:

1. Legal / regulated operating structure;
2. Accounting and sub-ledger model;
3. Direct Lending Liquidity Model, if the optional channel remains in scope;
4. Pilot scope and initial production policy values.
