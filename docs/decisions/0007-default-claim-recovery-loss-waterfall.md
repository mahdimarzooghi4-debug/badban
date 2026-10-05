# Decision 0007 — Default, Claim, Recovery, and Loss Waterfall

- **Status:** Proposed
- **Date:** 2026-10-05
- **Scope:** Business / Risk / Guarantee Operations / Recovery
- **Dependencies:** Decision 0003 — Asset Position Ownership by Funding Source; Decision 0005 — Hybrid Credit Delivery Model; Decision 0006 — External Lender Integration and Guarantee Lifecycle

## Problem

Badban can now reserve, issue, activate, monitor, and close guarantees for external lenders.

The remaining business question is what happens economically and operationally when the underlying credit becomes delinquent and an eligible lender claim is approved.

The original Badban proposal requires guarantee-risk management, repayment monitoring, a risk reserve, and limits on guarantee capacity, but it does not define a complete default waterfall.

Badban therefore needs one generic default and recovery model that is:

- compatible with participant-owned and program-attributed backing;
- usable with different external lenders;
- auditable;
- configurable by product and contract;
- explicit about who bears losses and who receives any recovery surplus.

## Proposed Decision

Badban shall separate two concepts:

1. **Claim Settlement Source** — how Badban obtains liquidity to satisfy an approved lender claim on time.
2. **Economic Loss Waterfall** — which economic resources ultimately absorb the loss after recovery and enforcement.

These are related but must not be treated as identical.

## 1. Default Preconditions

A missed payment does not automatically trigger asset liquidation or guarantee payment.

Before a claim can move to settlement, the applicable product/provider policy must define:

- delinquency threshold;
- cure / grace period;
- required lender collection actions;
- borrower notification requirements;
- evidence required for claim submission;
- claim filing window;
- calculation method for eligible outstanding balance;
- permitted fees or charges, if any.

A guarantee claim is payable only after Badban validates it under the immutable guarantee terms and policy version captured at issuance.

## 2. Generic Operational Flow

```
DELINQUENT
    ↓
CURE / COLLECTION
    ↓
CLAIM_PENDING
    ↓
CLAIM_VALIDATION
    ├─ REJECTED → continue lender/borrower resolution
    └─ APPROVED
          ↓
CLAIM_SETTLEMENT
          ↓
RECOVERY / ENFORCEMENT
          ↓
LOSS ALLOCATION
          ↓
SURPLUS / SHORTFALL TREATMENT
          ↓
CLOSED
```

## 3. Claim Settlement Source

Badban may need to pay an approved lender claim before the underlying backing asset has been liquidated or otherwise recovered.

Therefore an approved claim may be settled from an authorized **Guarantee Settlement / Risk Reserve** or other approved settlement liquidity source.

This is a liquidity mechanism, not an automatic statement that the reserve bears the final economic loss.

After claim settlement, Badban continues recovery against the backing and other contractually permitted recovery sources.

## 4. Economic Recovery Waterfall

Unless a provider/product policy explicitly defines a different approved structure, the proposed default economic waterfall is:

### Step 1 — Borrower Cure and Cash Recovery

Apply eligible cash received from the borrower toward the outstanding obligation under the lender/guarantee reconciliation rules.

### Step 2 — Enforce Specifically Encumbered Backing

Use or liquidate only the Asset Positions validly encumbered for that obligation, subject to:

- ownership policy;
- contract;
- legal/regulatory requirements;
- valuation and execution rules;
- applicable enforcement costs.

No unrelated participant asset may be used unless it was explicitly and validly cross-collateralized.

### Step 3 — Recover Claim Settlement Liquidity

If Badban already paid the lender from a settlement reserve, proceeds recovered from the borrower or backing first reimburse the amount economically advanced for the approved claim, subject to the contract and accounting policy.

### Step 4 — Apply Approved Guarantee Risk Reserve to Residual Covered Loss

If recovery from the borrower and encumbered backing is insufficient, the approved guarantee-risk reserve may absorb the eligible residual covered loss up to its policy and contractual limits.

### Step 5 — Residual Institutional Loss

Any remaining eligible loss after the approved reserve is exhausted or unavailable is allocated to the responsible Badban / guarantee vehicle / sponsor layer according to the governing contract and risk policy.

The system must never invent an additional participant liability merely because a loss remains.

## 5. Surplus Treatment

If enforcement produces value greater than the amount required to settle the secured obligation and permitted execution costs, the surplus must follow the ownership policy of the Asset Position.

### Participant-Owned Position

Residual value belongs to the participant or other legal owner after valid secured obligations and permitted costs are settled.

### Program-Attributed Position

Residual value remains within or returns to the applicable program / social-capital structure according to its policy, while any explicitly accrued participant entitlement is handled separately.

Badban must not treat enforcement surplus as general revenue by default.

## 6. Shortfall Treatment

If the backing value is insufficient:

- the participant is not automatically charged beyond obligations already validly created by the underlying loan and applicable law/contract;
- Badban's guarantee exposure is limited to the issued guarantee terms;
- uncovered lender loss remains with the party assigned that risk by the credit contract;
- reserve and institutional loss allocation must be explicit and versioned.

No product may silently convert a limited guarantee into an unlimited one.

## 7. Partial Guarantees

The model must support guarantee coverage below 100%.

For example:

```
Outstanding Eligible Principal = 100
Badban Guarantee Coverage = 70
Lender Uncovered Exposure = 30
```

Badban's maximum claim exposure is governed by the issued guarantee and applicable declining/fixed coverage rules, not merely by the lender's total outstanding balance.

Recovery-sharing rules between Badban and the lender must be explicit in the provider/product policy.

## 8. Recovery Allocation

Provider/product policy must define whether post-claim recoveries are allocated:

- first to Badban;
- first to lender uncovered exposure;
- pro rata;
- or by another approved contractual method.

This decision does **not** impose one universal post-claim recovery-sharing formula because that may vary by lender contract.

The selected method must be captured in the guarantee terms snapshot.

## 9. Asset Revaluation During Distress

When an obligation is delinquent or under claim:

- backing remains encumbered;
- valuation continues under the applicable Asset Type policy;
- material value deterioration may trigger risk actions defined by product policy;
- revaluation must not retroactively increase an already-issued guarantee beyond its approved terms.

## 10. Enforcement Controls

1. Enforcement requires an approved state transition and auditable authority.
2. Only validly encumbered backing may be enforced.
3. Enforcement quantity/value must be limited to what is required under the secured obligation and permitted costs.
4. Asset sale/realization price and execution costs must be recorded.
5. Surplus and shortfall calculations must be reproducible.
6. Participant-owned and program-attributed positions must remain distinguishable throughout enforcement.
7. No manual off-ledger settlement is permitted.
8. Related-party or conflicted asset disposal must be controlled by governance policy.
9. Claims and enforcement are subject to reconciliation before closure.
10. Closure requires final accounting of claim paid, recovery, reserve use, residual loss, and surplus.

## 11. Risk Reserve Role

The guarantee-risk reserve has three distinct possible functions:

- **liquidity:** timely payment of approved claims;
- **loss absorption:** coverage of eligible residual guarantee losses;
- **stability:** reducing disruption to Badban's broader operations and social-capital cycle.

Reserve sizing, target ratio, replenishment, minimum floor, and stress methodology require a separate Risk Appetite decision.

## 12. Direct Lending

If Badban itself is the lender, the same recovery and ownership principles apply, but there is no external lender claim payment.

The flow becomes:

```
DELINQUENT
   ↓
CURE / COLLECTION
   ↓
RECOVERY / ENFORCEMENT
   ↓
LOSS ALLOCATION
   ↓
CLOSED
```

Any direct-lending credit-loss reserve must be distinguished from the external-guarantee settlement reserve in accounting and risk reporting, even if governance later permits shared capital support.

## 13. Consequences

1. Risk reserve does not automatically protect an encumbered asset from enforcement.
2. Paying a lender claim from reserve does not mean the reserve bears the final loss before recovery.
3. Participant-owned surplus remains attributable to the participant/owner.
4. Program-attributed backing can remain within the social-capital cycle after settlement.
5. External lender contracts may vary in recovery-sharing, but every variation maps to the same generic lifecycle.
6. Badban can measure separately:
   - claim liquidity usage;
   - collateral recovery;
   - reserve loss;
   - institutional residual loss;
   - participant/program surplus.

## Follow-up Decisions

If Accepted, the next Business decisions should define:

1. **Asset-to-Credit / Guarantee Capacity Formula**;
2. **Risk Appetite and Reserve Sizing**;
3. **Credit Product Rules**;
4. **Return Allocation Policy**.
