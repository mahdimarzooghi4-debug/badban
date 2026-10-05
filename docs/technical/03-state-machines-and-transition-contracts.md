# Badban State Machines and Transition Contracts

- **Status:** Accepted
- **Date:** 2026-10-05
- **Stage:** Technical
- **Scope:** bounded external-lender pilot
- **Depends on:** Technical Foundation; System Context; Domain Aggregate Boundaries

## 1. Rule

Every lifecycle state change must occur through an explicit command with:

- allowed source state(s);
- target state;
- actor/authorization;
- business preconditions;
- external evidence where required;
- ledger effects;
- audit event;
- idempotency key where repeatable;
- failure reason code.

Arbitrary direct status mutation is forbidden.

## 2. GuaranteeCase State Machine

Primary path:

```
REQUESTED
   ↓ reserve
RESERVED
   ↓ legal issuance
ISSUED
   ↓ lender disbursement match
ACTIVE
   ├─ repayment/closure → RELEASED → CLOSED
   └─ delinquency → DELINQUENT
                    ↓ claim submit
                CLAIM_PENDING
                 ├─ reject → CLAIM_REJECTED
                 │            └─ resolve → ACTIVE / CLOSED
                 └─ approve → CLAIM_APPROVED
                               ↓
                         ENFORCEMENT / SETTLEMENT
                               ↓
                             CLOSED
```

Pre-activation terminal states:

- CANCELLED;
- EXPIRED.

### REQUESTED → RESERVED

Requires:

- participant/program eligible;
- valid ACTIVE Pilot Policy Pack;
- fresh authoritative valuation;
- calculated capacity >= requested amount;
- portfolio risk gate PASS;
- provider/product ACTIVE;
- legal authorization valid;
- backing reservation succeeds atomically.

Effects:

- create BackingAllocation;
- reduce available capacity;
- create reservation expiry;
- audit.

### RESERVED → ISSUED

Requires:

- reservation unexpired;
- Guarantee Issuer authorization valid;
- legal guarantee instrument/evidence verified;
- issued amount equals reserved amount unless an approved atomic amendment exists.

Effects:

- store legal guarantee identifier;
- snapshot terms/policy;
- mark legal issuance evidence;
- audit.

### ISSUED → ACTIVE

Requires:

- authoritative lender disbursement evidence;
- external loan ID present;
- disbursed principal exactly equals issued guarantee amount;
- provider/product still valid for activation;
- no blocking reconciliation/legal exception.

Hard invariant:

```
External Loan Principal = Issued Guarantee Amount
```

Effects:

- activate exposure;
- convert reserved backing to active encumbrance;
- create/update ExternalLoanMirror;
- journal/audit as required.

### ACTIVE → RELEASED

Requires:

- release amount supported by authoritative repayment/settlement evidence;
- product guarantee mode permits reduction/release;
- no pending claim;
- no blocking reconciliation mismatch.

Effects:

- reduce guarantee exposure;
- release matching backing capacity;
- journal/audit.

### ACTIVE → DELINQUENT

Requires:

- lender-authoritative delinquency evidence;
- product delinquency threshold met under captured product version.

No automatic claim payment occurs.

### DELINQUENT → CLAIM_PENDING

Requires:

- lender claim submission;
- required evidence present;
- claim within permitted filing rules;
- GuaranteeCase still eligible for claim review.

### CLAIM_PENDING → CLAIM_APPROVED

Requires:

- claim reconciliation complete;
- eligible amount calculated;
- approved amount <= eligible guarantee exposure;
- authorized approver;
- maker/checker if policy requires.

### CLAIM_PENDING → CLAIM_REJECTED

Requires:

- explicit reason code;
- supporting validation/evidence.

### CLAIM_APPROVED → ENFORCEMENT / SETTLEMENT

Requires:

- approved settlement source;
- ledger/settlement command accepted;
- enforcement authority where collateral action is required.

### RELEASED → CLOSED

Requires:

- guarantee exposure = 0;
- backing restriction released;
- loan/obligation authoritatively closed;
- no unresolved claim;
- required reconciliation MATCHED/RESOLVED.

## 3. BackingAllocation State Machine

```
AVAILABLE
  ↓ reserve
RESERVED
  ↓ activation
ENCUMBERED
  ├─ partial repayment → PARTIALLY_RELEASED
  ├─ full closure → RELEASED
  └─ claim/default → UNDER_ENFORCEMENT
                       ↓
                 REALIZED / RELEASED
```

Rules:

- allocated capacity cannot exceed available capacity;
- duplicate reservation idempotency returns original result;
- RELEASED cannot move back to ENCUMBERED without a new allocation;
- enforcement only references validly encumbered positions.

## 4. ExternalLoanMirror State Machine

```
PENDING
  ↓ authoritative disbursement
ACTIVE
  ├─ repayments → ACTIVE
  ├─ delinquency → DELINQUENT
  ├─ refinance/migration → REPLACED
  └─ authoritative settlement → SETTLED
```

Rules:

- state originates from lender evidence;
- Badban cannot locally invent disbursement or repayment;
- duplicate provider events do not duplicate principal changes;
- outstanding principal cannot go below zero;
- material provider correction is recorded as a correction event, not history rewrite.

## 5. Claim State Machine

```
SUBMITTED
  ↓ validation
UNDER_REVIEW
  ├─ REJECTED
  └─ APPROVED
       ↓
    SETTLEMENT_PENDING
       ↓
      PAID
       ↓
   RECOVERY_OPEN
       ↓
      CLOSED
```

Alternative:

- APPROVED may be partially settled only if policy explicitly allows it.

Rules:

- PAID does not mean final economic loss;
- recovery remains separately tracked;
- claim cannot be paid twice;
- rejected claims preserve evidence and reason.

## 6. RecoveryCase State Machine

```
OPEN
  ↓ recovery/enforcement action
IN_PROGRESS
  ├─ recovery received → IN_PROGRESS
  ├─ no further recovery possible → ALLOCATION_PENDING
  └─ asset realization → ALLOCATION_PENDING
                           ↓
                     LOSS_SURPLUS_ALLOCATED
                           ↓
                         CLOSED
```

Closure requires:

- all receipts posted;
- enforcement costs posted;
- recovery sharing allocated;
- reserve reimbursement determined;
- surplus/shortfall determined;
- final reconciliation complete.

## 7. PolicyPack State Machine

```
DRAFT
  ↓ authorized review
REVIEWED
  ↓ governance approval
APPROVED
  ↓ explicit activation
ACTIVE
  ├─ replacement → SUPERSEDED
  └─ retirement → RETIRED
```

Rules:

- only ACTIVE authorizes new real transactions;
- ACTIVE version immutable;
- no automatic activation on approval;
- historical transactions retain their version;
- only one active pilot policy pack per defined scope unless policy explicitly supports segmented scopes.

## 8. Provider Lifecycle

```
DRAFT
  ↓ due diligence complete
APPROVED
  ↓ activation
ACTIVE
  ├─ temporary issue → SUSPENDED
  ├─ authorization expiry → EXPIRED
  └─ relationship end → TERMINATED
```

Rules:

- only ACTIVE provider can create new exposure;
- SUSPENDED/EXPIRED/TERMINATED does not erase existing obligations;
- reactivation requires renewed authorization review.

## 9. Legal Authorization Lifecycle

```
PENDING_VERIFICATION
  ↓ verified
VALID
  ├─ temporary restriction → SUSPENDED
  ├─ date reached → EXPIRED
  ├─ revoked → REVOKED
  └─ superseded → SUPERSEDED
```

New regulated action requires VALID status and scope match.

## 10. ReconciliationCase State Machine

```
PENDING
  ↓ compare
  ├─ MATCHED
  ├─ MISMATCH
  ├─ STALE
  └─ DISPUTED
        ↓ resolution workflow
      RESOLVED
```

Rules:

- MISMATCH cannot become MATCHED without new comparison or explicit resolution evidence;
- critical mismatch can block issuance/release/claim/exit;
- original mismatch evidence remains immutable after RESOLVED.

## 11. ParticipantExitCase State Machine

```
ACTIVE
  ↓ eligibility
EXIT_ELIGIBLE
  ↓ initiate
EXIT_INITIATED
  ↓ reconcile
FINANCIAL_RECONCILIATION
  ├─ OBLIGATIONS_OPEN
  ├─ TRANSITION_SUPPORT_ACTIVE
  └─ READY_FOR_FINALIZATION
        ↓
      FINALIZED
```

Exceptional states:

- EXIT_SUSPENDED;
- LEGAL_HOLD;
- DECEASED;
- INCAPACITATED;
- TRANSFER_PENDING.

FINALIZED requires:

- ownership classification complete;
- releasable participant assets identified/released or scheduled;
- program-recyclable assets identified;
- future-financial entitlement determined;
- open obligations explicitly carried forward or closed;
- no unclassified balance;
- reconciliation evidence present.

## 12. ReturnAllocation State Machine

```
DRAFT
  ↓ calculate
CALCULATED
  ↓ review/approval
APPROVED
  ↓ journal posting
POSTED
  └─ correction → REVERSED
```

Rules:

- POSTED immutable;
- reversal creates linked financial correction;
- sum of allocation buckets must equal eligible net return;
- projected return never reaches POSTED without recognized source return.

## 13. Journal State

Journal entries use a narrow lifecycle:

```
PREPARED
  ↓ atomic validation/post
POSTED
```

Correction:

```
POSTED
  ↓ reversal command
POSTED + REVERSAL_POSTED
```

There is no editable posted state.

A PREPARED entry that cannot post is abandoned/failed without affecting balances.

## 14. Reservation Expiry

Reservation expiry is time-driven but must still execute as an explicit idempotent transition command.

```
RESERVED
  ↓ expiry time reached + not issued
EXPIRED
```

Effects:

- release reserved backing;
- restore available capacity;
- record expiry audit event.

Time passing alone must not leave backing permanently reserved.

## 15. Declining Guarantee Reduction

For a DECLINING product:

```
Authoritative Eligible Principal Repayment
→ Idempotent Repayment Event
→ Recalculate Current Guarantee Exposure
→ Release Corresponding Backing
```

Reduction must use the captured product/policy rule.

Elapsed time alone does not reduce exposure.

## 16. Fixed Guarantee Behavior

For FIXED products:

- repayment may update lender outstanding;
- guarantee exposure remains fixed until explicit contractual reduction/release event;
- no automatic backing release from ordinary installment passage.

## 17. Transition Command Contract

Every state-changing command should expose a standard internal contract:

- command ID;
- idempotency key;
- aggregate ID;
- expected aggregate version;
- actor;
- source;
- requested transition/action;
- effective timestamp if supplied;
- evidence references;
- policy reference;
- correlation ID;
- causation ID.

Response should include:

- resulting state;
- aggregate version;
- journal/audit references;
- domain events;
- reason code on rejection.

## 18. Optimistic Concurrency

State-changing commands must include or internally enforce an expected version.

On version conflict:

- do not auto-overwrite;
- re-read;
- re-evaluate preconditions;
- retry only when the command is still semantically valid.

## 19. Standard Rejection Codes

Technical APIs should use stable domain reason codes, for example:

- `POLICY_PACK_NOT_ACTIVE`;
- `VALUATION_STALE`;
- `CAPACITY_INSUFFICIENT`;
- `PORTFOLIO_RISK_RED`;
- `PROVIDER_NOT_ACTIVE`;
- `AUTHORIZATION_INVALID`;
- `RESERVATION_EXPIRED`;
- `LOAN_GUARANTEE_AMOUNT_MISMATCH`;
- `RECONCILIATION_BLOCK`;
- `CLAIM_NOT_ELIGIBLE`;
- `LEDGER_POSTING_FAILED`;
- `AGGREGATE_VERSION_CONFLICT`.

Human-readable messages can change; reason-code meaning must remain stable/versioned.

## 20. Next Technical Contract

The next Technical document should define the relational/data model and persistence constraints that enforce these aggregate and state-machine invariants.
