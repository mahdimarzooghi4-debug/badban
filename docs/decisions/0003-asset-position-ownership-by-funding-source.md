# Decision 0003 — Asset Position Ownership by Funding Source

- **Status:** Proposed
- **Date:** 2026-10-05
- **Scope:** Business / Product / Financial Rights
- **Dependencies:** Decision 0001 — Configurable Asset Input; Decision 0002 — Unified Asset and Credit Operator

## Problem

The original Badban proposal combines two ideas that need to be made explicit in the new model:

- capital can be attributed to a participant and managed in their name during the support period; and
- principal can later remain in or return to the social-capital cycle.

The evolving product also allows a participant to purchase or contribute an approved asset directly.

A single ownership rule cannot safely represent both cases.

## Proposed Decision

Badban should separate **Asset Type** from **Asset Position Ownership / Funding Source**.

Ownership and exit rights must be determined by the source and legal character of each asset position, not by whether the asset is gold or another Asset Type.

### A. Participant-Owned Position

Used when the participant purchases or contributes the asset with their own funds or transfers an asset they own into the Badban flow.

Proposed rules:

- the participant retains the economic ownership rights defined by contract;
- Badban or an approved custodian controls custody/encumbrance while the asset backs obligations;
- the asset may create credit capacity only while eligible, valued, available, and properly encumbered;
- after all secured obligations are satisfied, the remaining asset position is released to the participant;
- the position does **not** automatically become social capital at program exit.

### B. Program-Attributed Position

Used when a supporting institution or social-capital vehicle funds the backing for the participant.

Proposed rules:

- the position is attributed to a participant for defined benefits and credit capacity during eligibility;
- principal is not automatically withdrawable by the participant;
- ownership and custody remain with the program, designated vehicle, trustee, or other approved legal holder;
- participant entitlements are explicitly defined and auditable;
- at the end of eligibility, the remaining principal can be recycled under policy to support future participants;
- accrued participant entitlements, if any, are handled separately from principal.

### C. Other Sponsored / Contractual Positions

Badban may later support third-party-sponsored, employer-sponsored, family-funded, charitable, or other structures.

These must not be implemented as ambiguous exceptions. Each must map to an approved ownership/entitlement policy before becoming eligible.

## Core Rule

```
Asset Type ≠ Ownership Type
```

An Asset Type answers **what the asset is**.

An ownership/funding classification answers:

- who funded it;
- who owns it;
- who has beneficial rights;
- who may withdraw it;
- who may encumber it;
- what happens at exit;
- what happens after repayment;
- what happens after default.

These dimensions must be stored separately.

## Consequences

1. Gold can be participant-owned or program-attributed; the same applies to every other approved Asset Type.
2. Badban must model an **Asset Position**, not only an Asset Type.
3. Every Asset Position requires an explicit ownership/funding policy.
4. Credit capacity may be derived only from positions whose owner/holder has validly authorized the required backing or encumbrance.
5. Exit behavior cannot be derived from Asset Type.
6. The system must distinguish release-to-participant from recycle-to-social-pool.
7. Participant statements must clearly separate:
   - asset value;
   - participant-owned amount;
   - program-attributed amount;
   - encumbered amount;
   - available backing;
   - outstanding debt;
   - releasable amount.
8. Accounting and legal treatment remain subject to the final regulated/legal structure.

## Rationale

This split preserves the original social-capital recycling concept without confiscating or ambiguously treating assets that participants buy with their own money.

It also makes the product extensible: ownership semantics do not need to be redesigned whenever a new Asset Type is added.

## Source Tension Being Resolved

The original proposal states, in different sections, that capital is attributed to or belongs to the participant during membership while also stating that principal remains in or returns to the Badban cycle after exit.

The proposed two-position model makes those rights explicit instead of relying on one ambiguous definition of “participant capital.”

## Approval Gate

If Accepted, the next Business decision should define the **Loan Funding Model**, because the unified operator must have an explicit source of lending liquidity distinct from the collateral/backing model.
