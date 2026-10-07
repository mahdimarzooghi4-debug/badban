# Badban Reconciliation Engine Contract

- **Status:** Accepted
- **Date:** 2026-10-05
- **Stage:** Technical
- **Scope:** bounded external-lender pilot
- **Depends on:** Technical Foundation; Relational Data Model; Event Contracts; Provider Adapter Contracts; Decision 0015

## 1. Objective

Define how Badban independently verifies internal operational/financial state against authoritative external records.

Core rule:

```
Events provide timeliness.
Reconciliation provides independent control.
```

No provider integration is considered sufficient merely because callbacks or APIs appear reliable.

## 2. Reconciliation Domains

The pilot must support at least:

1. Custody / Asset Position reconciliation;
2. Lender / External Loan reconciliation;
3. Guarantee Issuer reconciliation;
4. Settlement / Cash reconciliation where Badban-controlled money moves;
5. Collateral Registry reconciliation where legal registration is required;
6. Ledger / Sub-ledger reconciliation;
7. Exit reconciliation before participant finalization.

## 3. Reconciliation Inputs

Each reconciliation compares two or more explicitly identified sources:

### Internal source

Examples:

- AssetPosition;
- BackingAllocation;
- GuaranteeCase;
- ExternalLoanMirror;
- GuaranteeClaim;
- reserve sub-ledger;
- JournalEntry/Posting;
- ExitCase.

### External source

Examples:

- custodian statement/snapshot;
- lender statement/snapshot;
- Guarantee Issuer register;
- bank/settlement statement;
- collateral registry state;
- legally valid provider evidence.

Every run must preserve the source timestamps and evidence references.

## 4. Snapshot Semantics

A reconciliation snapshot must have:

- source/provider;
- scope;
- snapshot timestamp;
- received timestamp;
- coverage interval where applicable;
- sequence/cursor/watermark where available;
- schema/mapping version;
- evidence reference;
- payload/content hash where applicable.

A reconciliation run must not compare states from incompatible cutoffs without recording that mismatch.

## 5. Reconciliation Case Lifecycle

```
PENDING
→ MATCHED
| MISMATCH
| STALE
| DISPUTED
→ RESOLVED
```

Rules:

- MATCHED means comparison succeeded under the applicable rules;
- MISMATCH means authoritative values/states materially differ;
- STALE means required comparison cannot be trusted because source freshness is outside allowed policy;
- DISPUTED means a discrepancy is under formal investigation with provider/owner;
- RESOLVED requires an explicit resolution path and evidence.

Original mismatch observations remain immutable after resolution.

## 6. Reconciliation Run

A reconciliation run records:

- run ID;
- reconciliation type;
- scope;
- provider;
- policy/rule version;
- started/finished timestamps;
- source cutoffs;
- counts by MATCHED/MISMATCH/STALE/DISPUTED;
- critical exception count;
- evidence references;
- run status.

Runs are append-only historical records.

## 7. Matching Keys

Matching uses explicit stable keys.

Examples:

### Lender

- provider ID + external loan ID;
- fallback business reference only if contractually unique.

### Guarantee Issuer

- issuer ID + external guarantee ID.

### Custodian

- custodian ID + custody account/reference + Asset Position mapping.

### Collateral Registry

- registry/operator ID + legal collateral registration ID.

### Settlement

- bank/payment provider + external settlement reference.

Fuzzy name-based matching is not permitted for financial closure.

## 8. Exact vs Tolerance Matching

Comparison rules are versioned and classify fields as:

### Exact

Must match exactly, for example:

- external loan ID;
- guarantee external ID;
- currency;
- legal entity/provider;
- state code where contract requires equality;
- one-to-one original principal/issued guarantee amount.

### Decimal Exact

Money/quantity compared using exact decimal arithmetic after normalized unit/currency rules.

### Tolerance-Based

Allowed only where an approved reconciliation policy explicitly defines a tolerance.

Examples may include provider rounding/statement presentation differences.

No tolerance value is invented by code.

### Policy Runtime binding (Decision 0039)

Comparison, materiality, blocking and freshness configuration belongs to the
distinct `RECONCILIATION_POLICY` PolicyVersion category. An ACTIVE Pilot Policy
Pack pins the exact reconciliation version through `component_version_ids`.
Resolve that pack first by existing exact-scope/effective-time rules, then require
exactly one matching reconciliation component among those pinned IDs. No latest,
policy-code/date fallback or default is permitted.

Required scope includes `pilot_scope` and `reconciliation_type`, derived from
authenticated/domain context. The caller must not arbitrarily select a more
permissive scope. Additional dimensions require accepted domain/provider
contracts. Pack approval/activation validates component approval proof,
immutability and canonical payload hash. DRAFT/REVIEWED components cannot
authorize runtime. Later component versions never rewrite an ACTIVE pack.

Use a strict schema with allowlisted canonical fields, stable rule codes,
EXACT/DECIMAL_EXACT/TOLERANCE_BASED/INFORMATIONAL modes, explicit materiality,
reason codes and explicit blocked-command mappings. Only TOLERANCE_BASED accepts
an explicit decimal-string tolerance; missing/invalid/float tolerance fails.
Other modes must not silently apply tolerance. No executable expression language.

Source freshness is explicit deterministic policy data with no default duration.
Required missing freshness or required missing blocking configuration fails
closed. No numeric materiality thresholds or production values are invented.
The loan/guarantee principal invariant remains code-enforced CRITICAL and cannot
be downgraded by policy. Every run captures pack/component IDs and versions,
payload hash, rule schema/version, and algorithm code/version alongside source
cutoffs/evidence. Decision 0039 authorizes only BL-042 and the minimal binding
extension after DoR; full human resolution remains BL-043.

### Informational

Differences recorded but not blocking.

## 9. Materiality

Every reconciliation rule has a materiality classification:

- INFO;
- WARNING;
- MATERIAL;
- CRITICAL.

Materiality determines workflow and blocking behavior.

Numeric materiality thresholds, if any, must come from an approved versioned policy pack.

## 10. Blocking Matrix

Reconciliation can block high-risk operations.

At minimum, policy must be able to map mismatch type/materiality to blocked commands.

Examples:

### Custody Critical Mismatch

May block:

- new capacity reservation;
- collateral release;
- enforcement completion;
- exit finalization.

### Lender Critical Mismatch

May block:

- guarantee exposure reduction;
- guarantee closure;
- claim approval;
- participant exit finalization.

### Guarantee Issuer Critical Mismatch

May block:

- activation;
- release;
- claim settlement;
- closure.

### Settlement Critical Mismatch

May block:

- marking payment as paid;
- reserve replenishment completion;
- recovery closure.

Blocking rules are explicit policy, never inferred ad hoc.

## 11. Custody Reconciliation

Compare:

```
Badban Asset Position / Restriction State
vs
Custodian Authoritative Position / Control State
```

At minimum compare:

- Asset Type;
- quantity;
- custody reference;
- ownership/control reference where available;
- restricted/encumbered state if custodian tracks it;
- release/realization state.

A missing external position for an internally available asset is CRITICAL unless policy explicitly classifies a transient provider lag.

## 12. Valuation Source Reconciliation

Where valuation is externally sourced, reconcile:

- source identity;
- observation timestamp;
- unit/quote basis;
- value;
- provider/source reference;
- data freshness.

This verifies source integrity, not guarantee-capacity arithmetic itself.

Capacity is recalculated deterministically from accepted valuation + policy.

## 13. Lender Reconciliation

Compare ExternalLoanMirror against lender authoritative state.

At minimum:

- external loan ID;
- original principal;
- currency;
- disbursement status/time;
- outstanding principal;
- repayments;
- delinquency state;
- settlement/closure state;
- provider event/snapshot cutoff.

Hard invariant:

```
Original External Loan Principal
=
Issued Badban Guarantee Amount
```

Any contrary authoritative lender record is CRITICAL.

## 14. Repayment Reconciliation

For each reconciliation window:

```
Lender Authoritative Repayment Set
vs
Processed External Loan Events
```

Detect:

- missing repayment in Badban;
- duplicate repayment in Badban;
- different amount;
- different external reference;
- correction/reversal not processed;
- out-of-order events.

Reconciliation may generate missing normalized events only through a controlled repair workflow; it must not silently mutate outstanding principal.

## 15. Guarantee Issuer Reconciliation

Compare GuaranteeCase against the legally authoritative issuer register.

At minimum:

- external guarantee ID;
- issued amount;
- issue date;
- beneficiary/lender;
- state;
- cancellation/release state;
- claim/settlement references where applicable.

Internal RESERVED state with no legal issuance is not a mismatch until issuance is expected.

Internal ISSUED/ACTIVE with absent external guarantee evidence is CRITICAL.

## 16. Collateral Registry Reconciliation

Where external legal registration is required, compare:

- internal BackingAllocation/restriction;
- external registration ID;
- registration state;
- encumbered asset/reference;
- secured amount/value where represented;
- release/enforcement state.

Badban must not report legal release complete until authoritative registry release is confirmed where required.

## 17. Settlement Reconciliation

Compare monetary journal/settlement workflow to bank/payment authoritative evidence.

At minimum:

- settlement reference;
- amount;
- currency;
- payer/payee role;
- value date;
- settlement state;
- reversal/correction.

A journal entry alone cannot satisfy external cash reconciliation.

## 18. Ledger vs Sub-ledger Reconciliation

Internal control must reconcile derived balances to journal truth.

Examples:

```
Participant Payable Projection
=
sum(posted journal postings for participant payable)
```

```
Future Financial Balance
=
vested posted entitlement
- posted payments/reversals
```

```
Reserve Cash Balance
=
posted reserve cash journal balance
```

Projection mismatch is a system-integrity issue.

## 19. Guarantee Exposure Reconciliation

Compare:

- GuaranteeCase.current_guarantee_exposure;
- BackingAllocation encumbered amount;
- memorandum/control ledger exposure;
- lender outstanding where DECLINING rules apply;
- claim/enforcement state.

No single projection may be treated as authoritative in isolation.

## 20. Claim Reconciliation

Before claim approval/settlement, reconcile:

- lender claim reference;
- current eligible guarantee exposure;
- external loan delinquency/outstanding;
- prior claim/settlement history;
- issuer claim state;
- backing/enforcement state.

Duplicate claim reference or claim amount above eligible exposure must block approval.

## 21. Recovery Reconciliation

Compare:

- RecoveryCase receipts;
- bank/settlement evidence;
- collateral realization proceeds;
- allocation postings;
- reserve reimbursement;
- final residual loss.

Before RecoveryCase closes:

```
Claim Settlement
=
Recovered Amount
+ Open Pending Recovery
+ Final Residual Loss
```

subject to explicitly modeled enforcement costs/allocation treatment.

## 22. Exit Reconciliation

ParticipantExitCase finalization requires a reconciliation checklist covering:

- participant-owned positions;
- program-attributed positions;
- active guarantees;
- external loans;
- claims/recoveries;
- future-financial entitlements;
- unpaid participant payables;
- releasable/recyclable balances;
- legal holds;
- unresolved material reconciliation cases.

No FINALIZED state while mandatory CRITICAL/MATERIAL items remain unresolved, unless an explicit approved carried-forward obligation is part of the exit contract.

## 23. Reconciliation Scheduling

Reconciliation may run:

- event-triggered;
- near-real-time;
- periodic;
- end-of-day;
- on-demand;
- before high-risk commands.

Cadence is policy/provider-specific.

No universal interval is hard-coded.

## 24. Pre-Command Reconciliation Gate

High-impact commands may require a fresh reconciliation status.

Examples:

- activate guarantee;
- reduce/release exposure;
- settle claim;
- release collateral;
- finalize exit.

The command checks:

- reconciliation type;
- required status;
- freshness;
- materiality.

If insufficient:

`RECONCILIATION_BLOCK`

or:

`EXTERNAL_STATE_STALE`

## 25. Staleness

Each reconciliation type has an approved freshness policy.

A case becomes STALE when authoritative evidence is older than the permitted window.

Stale data must never be silently treated as MATCHED.

## 26. Resolution Paths

Every mismatch resolution must be classified.

Allowed categories include:

### INTERNAL_CORRECTION

Badban internal state was wrong; fix via valid domain correction/reversal command.

### EXTERNAL_CORRECTION

Provider confirms its state was wrong and supplies authoritative correction.

### LATE_EVENT_APPLIED

Missing provider event is authenticated/deduplicated and processed through normal command flow.

### MAPPING_CORRECTION

Adapter mapping/schema interpretation was wrong; new version is applied prospectively plus controlled historical correction where authorized.

### ACCEPTED_DIFFERENCE

Difference is valid under an approved rule/tolerance.

### DISPUTE_OUTCOME

Formal dispute concluded with evidence.

No resolution type may directly overwrite immutable journal/audit/event history.

## 27. Maker-Checker for Resolution

Material/critical reconciliation resolutions should support maker-checker.

The actor proposing resolution cannot approve their own resolution where policy requires separation.

Resolution stores:

- proposed by;
- approved by;
- reason;
- evidence;
- correction command references;
- timestamps.

## 28. Manual Reconciliation

Manual provider statements/files may be used only if:

- source is authenticated/controlled;
- file/hash/reference preserved;
- operator identified;
- parsing/mapping version recorded;
- row-level result available;
- high-impact resolution receives required approval.

Manual does not mean informal.

## 29. Reconciliation Repair Workflow

The engine may propose repairs but must not directly edit financial state.

Example:

```
Mismatch detected
→ propose missing repayment event
→ authorized repair command
→ inbox/domain processing
→ new reconciliation run
→ MATCHED
```

Repairs must use normal domain commands and idempotency.

## 30. Reconciliation Evidence

Every case/run should preserve references to:

- internal snapshot/reference;
- external snapshot/reference;
- compared fields;
- difference payload;
- mapping/rule version;
- evidence hash where appropriate.

Sensitive evidence may remain in secure storage with immutable reference.

## 31. No Self-Reconciliation

An integration event being processed successfully does not itself count as independent reconciliation.

For high-value external relationships, reconciliation should use a separately fetched/provider-issued snapshot or statement where possible.

## 32. Provider Unavailability

If provider reconciliation source is unavailable:

- mark reconciliation STALE/PENDING as appropriate;
- record outage;
- do not infer MATCHED from last known state beyond freshness policy;
- apply blocking policy to unsafe actions.

Existing obligations remain visible and serviceable where possible.

## 33. Batch Reconciliation Algorithm

Logical flow:

```
load internal scope snapshot
load authoritative external snapshot
normalize both using versioned rules
match by stable identifiers
compare exact/tolerance fields
classify differences
persist observations/cases
apply materiality
update blocking projections
emit audit/event
```

Reconciliation itself must be idempotent for the same source snapshot/rule version.

## 34. Incremental Reconciliation

When provider supports cursor/sequence:

- store last successfully reconciled watermark;
- fetch next range;
- detect gaps;
- process in deterministic order;
- advance watermark only after successful persistence.

Never skip a failed batch silently.

## 35. Reconciliation Persistence Additions

### reconciliation_runs

- id;
- type;
- provider_id nullable;
- scope_definition;
- rule_version;
- internal_cutoff;
- external_cutoff;
- source_snapshot_ref;
- status;
- started_at;
- finished_at;
- matched_count;
- mismatch_count;
- stale_count;
- critical_count.

### reconciliation_cases

Already defined; extend with:

- run_id;
- materiality;
- blocking_scope;
- rule_version;
- first_detected_at;
- last_observed_at;
- resolved_at;
- resolution_type.

### reconciliation_observations

Append-only comparison detail.

### reconciliation_blocks

Derived/current control projection:

- id;
- reconciliation_case_id;
- blocked_command_type;
- resource_type/id;
- active;
- activated_at;
- cleared_at.

Blocks are projections from unresolved cases and policy.

## 36. Reconciliation APIs

Existing Technical 07 endpoints remain, with logical support for:

```
POST /api/v1/reconciliation/runs
GET  /api/v1/reconciliation/runs/{id}
GET  /api/v1/reconciliation/cases
GET  /api/v1/reconciliation/cases/{id}
POST /api/v1/reconciliation/cases/{id}/propose-resolution
POST /api/v1/reconciliation/cases/{id}/approve-resolution
POST /api/v1/reconciliation/cases/{id}/recheck
```

No generic "mark matched" endpoint.

## 37. Reconciliation Events

Emit:

- `ReconciliationRunStarted`
- `ReconciliationRunCompleted`
- `ReconciliationMismatchDetected`
- `ReconciliationBecameStale`
- `ReconciliationResolutionProposed`
- `ReconciliationResolved`
- `ReconciliationBlockActivated`
- `ReconciliationBlockCleared`

All are append-only events.

## 38. Standard Reason Codes

Examples:

- `RECON_EXTERNAL_RECORD_MISSING`
- `RECON_INTERNAL_RECORD_MISSING`
- `RECON_AMOUNT_MISMATCH`
- `RECON_STATE_MISMATCH`
- `RECON_IDENTIFIER_MISMATCH`
- `RECON_DUPLICATE_EXTERNAL_RECORD`
- `RECON_SEQUENCE_GAP`
- `RECON_SOURCE_STALE`
- `RECON_MAPPING_MISMATCH`
- `RECON_SETTLEMENT_MISSING`
- `RECON_COLLATERAL_STATE_MISMATCH`
- `RECON_GUARANTEE_LOAN_PRINCIPAL_MISMATCH`

## 39. Observability

Metrics include:

- reconciliation run success/failure;
- lag by provider/type;
- mismatch counts by materiality;
- oldest unresolved critical case;
- blocking case count;
- stale source count;
- mean/median time to resolution;
- repeated mismatch recurrence;
- repair command success/failure.

## 40. Test Contract

Tests must cover:

- exact match;
- missing external record;
- missing internal record;
- duplicate record;
- amount mismatch;
- state mismatch;
- stale snapshot;
- mismatched cutoff;
- tolerance-accepted difference;
- critical block activation;
- resolution + block clearing;
- duplicate reconciliation run;
- provider outage;
- late event repair;
- mapping correction;
- exit finalization blocked by unresolved case.

Financial reconciliation tests must verify no reconciliation workflow directly mutates immutable journal/event history.

## 41. Hard Invariants

1. Reconciliation compares explicit authoritative sources with recorded cutoffs.
2. MATCHED is never inferred from provider silence.
3. Stale source is never treated as matched.
4. Critical mismatches can block high-risk commands.
5. No mismatch is resolved by direct balance/status editing.
6. Repairs use normal domain commands and ledger rules.
7. Original mismatch evidence remains immutable.
8. One-to-one loan/guarantee mismatch is always critical.
9. Real cash completion requires settlement reconciliation where applicable.
10. Exit cannot finalize with unresolved required material/critical reconciliation items.

## 42. Next Technical Contracts

Next:

1. Identity, RBAC, and Maker-Checker Contract;
2. Security and Secrets Contract;
3. Observability and Operational Readiness Contract;
4. Deployment / Runtime Topology and Non-Functional Requirements.
