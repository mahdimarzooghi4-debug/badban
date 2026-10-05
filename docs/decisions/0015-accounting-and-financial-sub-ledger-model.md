# Decision 0015 — Accounting and Financial Sub-Ledger Model

- **Status:** Proposed
- **Date:** 2026-10-05
- **Scope:** Business / Accounting Architecture / Financial Control / Reconciliation
- **Dependencies:** Decision 0003 — Asset Position Ownership by Funding Source; Decision 0006 — External Lender Integration and Guarantee Lifecycle; Decision 0007 — Default, Claim, Recovery, and Loss Waterfall; Decision 0008 — Policy-Driven Asset-to-Guarantee Capacity Formula; Decision 0010 — Risk Appetite and Guarantee Reserve Framework; Decision 0012 — Policy-Driven Return Allocation; Decision 0013 — Participant Exit and Entitlement Rules; Decision 0014 — Regulated Operating Structure and Legal-Role Separation

## Problem

Badban now has explicit business rules for:

- participant-owned and program-attributed assets;
- valuation and guarantee capacity;
- external lending;
- guarantees and claims;
- reserve usage;
- recovery and enforcement;
- return allocation;
- participant exit;
- legal-role separation.

The product now needs one accounting architecture that preserves economic ownership and transaction history without mixing:

- participant assets;
- program assets;
- guarantee reserve;
- external lender obligations;
- guarantee exposure;
- claim-settlement cash;
- recovery proceeds;
- return allocations;
- future-financial balances;
- Badban corporate funds.

The accounting model must also work when different regulated legal entities perform different roles.

## Proposed Decision

Badban shall maintain an **append-only financial sub-ledger architecture** using double-entry postings for Badban-controlled economic balances and explicit mirror/reference ledgers for externally owned obligations.

The Badban product ledger is the authoritative operational/economic record for the Badban platform.

It does **not** automatically replace:

- the statutory general ledger of Badban's legal entity;
- the lender's accounting ledger;
- the guarantee issuer's statutory books;
- a custodian's books;
- a capital-market provider's books;
- legally required external registries.

Every product-ledger balance must map to an identified economic owner and legal role.

## 1. Core Accounting Rule

```
Every financial event
→ immutable journal entry
→ balanced postings
→ derived balances
```

No business balance may be directly edited.

Corrections must use:

- reversal;
- compensating entry;
- approved adjustment event.

Historical entries remain immutable.

## 2. Legal-Entity Boundary

The ledger model must preserve **who legally owns or owes each balance**.

At minimum, each posting must carry:

- legal entity;
- economic owner;
- participant/program context;
- account;
- currency;
- amount;
- transaction/event reference;
- effective timestamp;
- posting timestamp;
- policy version where relevant.

A balance belonging to a participant, program, reserve vehicle, lender, or guarantee issuer must not be presented as Badban corporate property merely because Badban records it.

## 3. Required Sub-Ledgers

Badban shall maintain distinct sub-ledgers for at least the following domains.

### A. Asset Position Sub-Ledger

Tracks the economic asset position.

Required dimensions include:

- participant/program;
- Asset Type;
- ownership/funding type;
- legal owner;
- custodian/holder;
- quantity;
- acquisition/source reference;
- accounting value where applicable;
- latest valuation reference;
- status;
- restricted/available quantity.

This ledger distinguishes **asset quantity/ownership** from **market valuation**.

Market price changes must not rewrite historical acquisition/posting entries.

### B. Valuation Sub-Ledger / Valuation Record

Tracks point-in-time valuations used for:

- statements;
- guarantee capacity;
- risk;
- enforcement.

Each valuation record must preserve:

- Asset Position;
- quantity valued;
- price;
- FX conversion if applicable;
- source;
- valuation timestamp;
- policy version.

Valuation is a measurement layer and must not be confused with a cash transaction.

### C. Encumbrance / Collateral Sub-Ledger

Tracks how much of each Asset Position is:

- available;
- reserved;
- pledged/encumbered;
- under claim;
- under enforcement;
- released.

It must link every restriction to the exact:

- guarantee reservation;
- guarantee instrument;
- loan/facility;
- claim;
- legal collateral registration where applicable.

This ledger prevents double-use of backing.

### D. Guarantee Exposure Sub-Ledger

Tracks each Badban guarantee obligation.

For external lending:

```
Original External Loan Principal
= Original Issued Guarantee Amount
```

under Decision 0009.

The guarantee ledger must record:

- guarantee issuer;
- lender;
- participant;
- product;
- original guarantee amount;
- current exposure;
- fixed/declining mode;
- claim state;
- settlement state;
- backing allocation;
- policy versions.

The product ledger must track the economic guarantee exposure even when the statutory accounting treatment belongs to a separate licensed Guarantee Issuer.

### E. External Loan Mirror Sub-Ledger

For external lenders, Badban shall maintain a synchronized mirror of lender-reported loan state.

It must track:

- lender of record;
- external loan identifier;
- original principal;
- current outstanding principal;
- repayment schedule/reference;
- repayments;
- delinquency;
- settlement;
- authoritative synchronization timestamp.

This is a **mirror/reference ledger**.

The external bank/fund loan is not automatically a Badban corporate receivable merely because Badban mirrors it operationally.

### F. Guarantee Reserve Sub-Ledger

Tracks reserve resources separately from participant assets and program principal.

It must distinguish:

- claim-settlement liquidity;
- expected-loss reserve where used;
- stress/capital buffer where used;
- reserve contribution source;
- reserve draw;
- reserve replenishment;
- recoveries credited back.

Participant-owned collateral must never be reclassified into general guarantee reserve solely because it secures an obligation.

### G. Claim Settlement Sub-Ledger

Tracks approved guarantee claims from approval through settlement.

Required states/amounts include:

- claim requested;
- eligible amount;
- rejected amount;
- approved amount;
- amount paid;
- settlement source;
- unpaid approved amount;
- recovery linked to claim;
- final residual loss.

Claim payment and final economic loss are distinct accounting events.

### H. Recovery Sub-Ledger

Tracks all post-default recoveries, including:

- participant cash cure;
- collateral-sale proceeds;
- insurance/third-party recovery where applicable;
- reserve reimbursement;
- lender recovery-sharing;
- participant/program surplus;
- residual shortfall.

Every recovery must link to the claim/exposure that caused it.

### I. Return Allocation Sub-Ledger

Tracks Decision 0012 allocations separately by bucket:

- risk reserve;
- livelihood;
- future financial;
- capital growth;
- social reinvestment;
- carry-forward.

Each allocation event must balance exactly to the source eligible return.

### J. Future Financial Entitlement Sub-Ledger

Tracks participant future-financial rights separately from:

- principal;
- livelihood payments;
- program capital;
- projected returns.

It must record:

- vested amount;
- unvested amount;
- paid amount;
- remaining amount;
- payout schedule;
- expiry/suspension state where applicable.

### K. Program Capital Sub-Ledger

Tracks capital belonging to the supporting program/social-capital structure.

It must distinguish:

- program-funded principal;
- participant attribution;
- capital growth;
- recycled capital;
- social-reinvestment contributions;
- current participant assignment;
- availability for reassignment.

Program attribution is not equivalent to participant ownership.

### L. Corporate Funds Sub-Ledger

Tracks Badban corporate money separately from:

- participant money;
- program capital;
- reserves;
- settlement funds;
- lender money.

Operating expenses, corporate revenue, capital contributions, and corporate cash must never be silently mixed with client/program balances.

## 4. Direct Lending Sub-Ledger

Badban Direct Lending remains disabled until the legal gate in Decision 0014 is passed.

If enabled later, the accounting model must add distinct ledgers for:

- direct-lending liquidity;
- direct-loan receivables;
- direct-loan principal repayment;
- direct-credit income/fees;
- direct-credit loss reserve;
- charge-off/recovery.

These must remain distinct from external-lender mirror balances.

## 5. Account Ownership Dimensions

Every balance-bearing account must support explicit dimensions for:

- legal owner;
- beneficial owner where different;
- funding source;
- participant;
- program;
- provider;
- legal entity;
- Asset Type;
- product;
- currency;
- restriction/encumbrance status.

Badban must not use one generic “participant balance” field for economically different rights.

## 6. Money vs Asset Quantity

Badban must distinguish:

1. **Monetary ledgers** — balances in a currency;
2. **Asset quantity ledgers** — units/grams/shares/etc.;
3. **Valuation records** — currency value of an asset quantity at a point in time.

Example:

```
10 grams gold
≠
current valuation of 10 grams
≠
guarantee capacity derived from that valuation
```

These are three different records.

## 7. Book Value vs Market Value

Where an accounting book value is required, it must be stored separately from operational market valuation.

The product must not overwrite a historical/accounting value merely because market price changes.

Statutory accounting measurement rules depend on the legal entity, accounting standards, asset type, and final professional accounting policy and are not fixed by this decision.

## 8. External Money Movement

Every real movement of money must reference an authoritative settlement record such as:

- bank transaction;
- payment instruction;
- custodian settlement;
- lender disbursement;
- reserve payment;
- recovery receipt.

A ledger entry alone must not falsely imply that money moved externally.

Likewise, external settlement without a corresponding reconciled ledger event is an exception state.

## 9. Transaction Atomicity

A business event that affects multiple sub-ledgers must post atomically from a business perspective.

Example — guarantee activation:

```
Loan activation confirmation
        ↓
Guarantee becomes ACTIVE
        ↓
Backing becomes encumbered
        ↓
External loan mirror becomes active
        ↓
Guarantee exposure recognized
```

The system must not leave these records partially posted without a recoverable exception workflow.

## 10. Reconciliation

Badban shall operate scheduled reconciliation against authoritative external providers.

At minimum:

### Custody Reconciliation

Internal Asset Positions
vs
custodian/registry positions.

### Lender Reconciliation

External Loan Mirror
vs
lender-reported outstanding state.

### Guarantee Reconciliation

Badban guarantee lifecycle
vs
legal Guarantee Issuer records.

### Bank/Settlement Reconciliation

Internal cash/sub-ledger movements
vs
bank/payment settlement records.

### Collateral Registry Reconciliation

Internal encumbrance
vs
external legal collateral registry, where required.

Unreconciled differences must be visible as exceptions.

## 11. Reconciliation State

Every externally dependent balance or obligation should have a reconciliation state such as:

- MATCHED;
- PENDING;
- MISMATCH;
- STALE;
- DISPUTED.

A critical MISMATCH or STALE state may block:

- new guarantee issuance;
- release of backing;
- claim payment;
- participant exit finalization;

according to policy.

## 12. Journal Event Identity

Every journal event must have:

- globally unique event ID;
- business event type;
- source system;
- source reference;
- idempotency key;
- effective timestamp;
- posting timestamp;
- actor/system identity;
- approval reference where required.

Duplicate external events must not create duplicate financial postings.

## 13. Reversal and Correction

Financial history must never be silently rewritten.

Corrections use:

```
Original Entry
+ Reversal Entry
+ Corrected Entry
```

or another approved compensating-entry method.

The reason, actor, and approval must be retained.

## 14. Period Close

Badban should support controlled financial periods.

A closed period cannot accept ordinary backdated edits.

Late-arriving events must follow an approved:

- current-period adjustment;
- controlled reopen;
- prior-period adjustment;

process.

The exact statutory accounting treatment is determined by the accounting policy of the responsible legal entity.

## 15. Return Posting Example

Conceptually:

```
Recognized Eligible Net Return
        ↓
Risk Reserve Allocation
        +
Livelihood Payable
        +
Future Financial Balance
        +
Capital Growth
        +
Social Reinvestment
        +
Approved Carry Forward
```

The allocation event must balance completely.

If capital growth is capitalized into an Asset Position, the posting must clearly show the transfer from allocable return into capitalized principal/value.

## 16. Claim and Recovery Example

Conceptually:

### Claim Settlement

```
Approved Claim
        ↓
Reserve / Settlement Source Draw
        ↓
Payment to Lender
        ↓
Recovery Receivable / Recovery Process
```

### Later Recovery

```
Borrower / Collateral Recovery
        ↓
Recovery Allocation
        ├─ reimburse settlement source
        ├─ lender share where contractually applicable
        ├─ participant/program surplus
        └─ residual loss
```

Badban must preserve the difference between:

- cash paid;
- amount recovered;
- final loss.

## 17. Exit Accounting

Decision 0013 exit finalization requires a reconciled financial statement.

The accounting model must be able to identify:

- releasable participant-owned assets;
- recyclable program capital;
- vested unpaid entitlement;
- restricted collateral;
- open guarantee exposure;
- unresolved claim/recovery;
- carry-forward/post-exit balances.

No exit may be finalized from an aggregate balance that hides these categories.

## 18. Statements and Reporting

Badban should generate separate views for different audiences.

### Participant Statement

Shows only participant-relevant rights and obligations in understandable form.

### Program Statement

Shows program capital, allocations, recycling, participant attribution, and performance.

### Guarantee/Risk Statement

Shows exposure, reserves, claims, recoveries, concentrations, and risk ratios.

### Legal Entity Accounting Export

Provides the mappings needed by the responsible legal entity's statutory accounting system.

### Audit Trail

Provides immutable event/posting history and reconciliation evidence.

## 19. Chart of Accounts vs Product Account Taxonomy

Badban shall separate:

- **Product Account Taxonomy** — stable business concepts used by the platform;
- **Legal Entity Chart of Accounts Mapping** — accounting-code mapping for each responsible legal entity.

This allows the product model to remain stable even if:

- a guarantee issuer changes;
- a custodian changes;
- accounting chart codes differ;
- a new legal vehicle is added.

## 20. Multi-Currency

If Badban later supports more than one currency:

- original transaction currency must be preserved;
- reporting/base-currency conversion is separate;
- FX source and timestamp must be stored;
- realized and unrealized FX effects must not be guessed.

No multi-currency accounting behavior is activated without an approved accounting policy.

## 21. Audit and Control

At minimum, the financial ledger must support:

- maker/checker approval where policy requires;
- immutable journal history;
- role-based posting authority;
- period-close controls;
- exception queues;
- reconciliation evidence;
- exportable audit trail;
- traceability from statement line to journal event to external evidence.

## 22. Non-Negotiable Controls

1. No direct balance mutation.
2. Every monetary journal entry balances.
3. Asset quantity, valuation, and guarantee capacity are separate concepts.
4. Participant, program, reserve, lender, guarantor, and corporate balances are never silently commingled.
5. External lender loans are mirrored operationally and are not automatically treated as Badban corporate receivables.
6. Claim payment and final loss are separate.
7. Participant collateral is not general reserve.
8. Corrections are auditable reversals/adjustments.
9. External-settlement-dependent events require reconciliation.
10. Statutory accounting treatment is determined by the responsible legal entity's approved accounting policy, not guessed by Badban Core.

## Parameters Deliberately Not Fixed Here

This decision does not determine:

- statutory chart-of-account codes;
- tax treatment;
- accounting-standard classification;
- revenue recognition rules;
- impairment methodology;
- provisioning percentages;
- fair-value accounting rules;
- statutory guarantee-liability classification;
- legal-entity consolidation treatment.

These require the final legal structure and professional accounting policy.

## Consequences

1. Financial ownership remains explicit across all Badban flows.
2. Product balances become reproducible from immutable journal events.
3. External providers can be reconciled without mixing their books with Badban's.
4. Audit and regulatory reporting become technically supportable.
5. Participant statements can be derived without exposing internal accounting complexity.
6. The Technical stage will need a ledger/journal architecture, reconciliation engine, provider adapters, and legal-entity accounting mappings.

## Follow-up

If Accepted, the remaining Business-stage decisions should focus on:

1. **Direct Lending Liquidity Model** — only if the optional direct-lending channel remains in pilot scope;
2. **Pilot Boundary and Initial Policy Values**;
3. **Business-stage completion review** before Technical architecture begins.
