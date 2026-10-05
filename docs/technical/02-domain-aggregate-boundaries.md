# Badban Domain Aggregate Boundaries

- **Status:** Proposed
- **Date:** 2026-10-05
- **Stage:** Technical
- **Scope:** bounded external-lender pilot
- **Depends on:** Technical Foundation; System Context and Trust Boundaries

## 1. Aggregate Design Rule

Badban aggregates exist to enforce business invariants, not to mirror database tables.

An aggregate boundary should contain only data that must be changed consistently in one local transaction.

Cross-aggregate coordination occurs through application services and domain events, with explicit policy and idempotency.

## 2. Participant Aggregate

### Root

**ParticipationEpisode**

### Owns

- participant ID reference;
- program ID;
- enrollment status;
- eligibility reference;
- consent/disclosure state;
- support-program status;
- entry/exit timestamps;
- exit state reference.

### Invariants

- one participation episode has one program;
- closed episodes are immutable except controlled correction metadata;
- re-entry creates a new episode;
- participant financial balances are not stored here.

## 3. AssetPosition Aggregate

### Root

**AssetPosition**

### Owns

- Asset Type reference;
- participant/program attribution;
- ownership/funding type;
- legal owner reference;
- custodian reference;
- quantity;
- unit;
- lifecycle status;
- restriction summary;
- provenance/source reference.

### Invariants

- ownership/funding type is explicit;
- quantity cannot become negative;
- ownership cannot be silently changed;
- position cannot be released while linked active restrictions remain;
- market valuation is not stored as mutable position truth.

### Does not own

- current valuation;
- guarantee capacity;
- guarantee exposure;
- external legal collateral state.

## 4. Valuation Aggregate

### Root

**ValuationObservation**

### Owns

- Asset Position reference;
- valued quantity;
- price/value;
- currency;
- source;
- observed timestamp;
- received timestamp;
- FX reference where applicable;
- valuation policy version;
- freshness result.

### Invariants

- immutable after acceptance;
- source must be approved for Asset Type;
- timestamps must be timezone-aware;
- stale observation may remain historical but cannot create new capacity.

## 5. PolicyPack Aggregate

### Root

**PolicyPackVersion**

### Owns

- policy-pack ID/version;
- lifecycle state;
- effective interval;
- Asset Type policy references;
- risk policy references;
- provider/product policy references;
- return-allocation policy references;
- approver;
- approval timestamp.

### Invariants

- only ACTIVE versions authorize real pilot transactions;
- approved versions are immutable;
- activation is explicit;
- historical transactions keep the version used at decision time;
- superseding a policy does not rewrite history.

## 6. CreditProvider Aggregate

### Root

**CreditProvider**

### Owns

- legal entity reference;
- provider status;
- supported integration modes;
- product references;
- authorization review state;
- operational contact/reference;
- suspension reason.

### Invariants

- suspended/expired provider cannot create new exposure;
- legal authorization must be valid for active regulated use;
- provider identity cannot be inferred from product text.

## 7. CreditProduct Aggregate

### Root

**CreditProductVersion**

### Owns

- provider reference;
- product ID/version;
- amount limits;
- tenor rules;
- repayment rules;
- fee/pricing metadata;
- guarantee exposure mode;
- delinquency/claim rules;
- lifecycle state.

### Invariants

- each version belongs to exactly one provider;
- active obligations retain captured version;
- missing mandatory terms block activation;
- one-to-one principal/guarantee rule is not configurable away for the pilot.

## 8. Guarantee Aggregate

### Root

**GuaranteeCase**

### Owns

- participant;
- provider/product references;
- requested principal;
- reserved guarantee amount;
- issued guarantee amount;
- guarantee mode;
- lifecycle state;
- reservation expiry;
- legal guarantee evidence/reference;
- external loan reference;
- claim references;
- policy snapshots.

### Key States

- REQUESTED;
- RESERVED;
- ISSUED;
- ACTIVE;
- DELINQUENT;
- CLAIM_PENDING;
- CLAIM_APPROVED;
- CLAIM_REJECTED;
- ENFORCEMENT;
- RELEASED;
- CLOSED;
- CANCELLED;
- EXPIRED.

### Invariants

- reserved amount cannot exceed approved available capacity;
- issued amount cannot exceed reserved amount unless reservation is atomically amended;
- external loan principal must equal issued guarantee amount at activation;
- ACTIVE requires authoritative legal issuance and disbursement evidence;
- CLOSED requires no unresolved claim/reconciliation;
- release cannot exceed previously encumbered capacity.

## 9. BackingAllocation Aggregate

### Root

**BackingAllocation**

This aggregate records how guarantee capacity is sourced from one or more Asset Positions.

### Owns

- GuaranteeCase reference;
- Asset Position allocations;
- capacity amount per position;
- reservation/encumbrance state;
- release amount per position;
- allocation policy version.

### Invariants

- sum of position allocations equals guarantee capacity consumed by the allocation;
- no Asset Position capacity unit can be allocated twice beyond available capacity;
- release is monotonic and cannot exceed allocated amount;
- backing allocation is explicit enough for claim/enforcement traceability.

### Transactional note

Reservation of backing must use concurrency control across affected Asset Positions.

Implementation may coordinate using locked capacity records rather than loading all positions into one in-memory aggregate.

## 10. ExternalLoanMirror Aggregate

### Root

**ExternalLoanMirror**

### Owns

- provider;
- external loan ID;
- GuaranteeCase reference;
- original principal;
- outstanding principal;
- disbursement state;
- schedule/reference;
- repayment events;
- delinquency state;
- last provider event timestamp;
- synchronization status.

### Invariants

- original principal equals issued guarantee amount for pilot activation;
- repayment event is idempotent by provider event/reference;
- outstanding principal cannot be reduced twice by duplicate event;
- provider-reported state is preserved, not overwritten by inferred values.

## 11. PortfolioRisk Aggregate

### Root

**PortfolioRiskSnapshot**

### Owns

- exposure metrics;
- concentration metrics;
- reserve requirement;
- reserve availability reference;
- stress metrics;
- GREEN/AMBER/RED state;
- policy version;
- evaluation timestamp.

### Invariants

- snapshot is immutable;
- issuance decision references a specific risk snapshot/version;
- RED blocks exposure increase;
- participant-level capacity cannot override RED.

## 12. Reserve Aggregate

### Root

**GuaranteeReserveAccount**

### Owns operational reserve classification:

- settlement liquidity;
- expected-loss reserve;
- stress/capital buffer;
- available amount;
- committed amount;
- draw references;
- replenishment references.

### Invariants

- participant-owned collateral is never a general reserve balance;
- reserve draw requires an approved business event;
- reserve balance changes only through ledger-backed events.

The ledger remains the financial source for posted reserve balances.

## 13. Claim Aggregate

### Root

**GuaranteeClaim**

### Owns

- GuaranteeCase reference;
- lender claim reference;
- requested amount;
- eligible amount;
- approved/rejected amount;
- evidence references;
- validation results;
- decision state;
- settlement state;
- recovery linkage.

### Invariants

- claim cannot be approved solely from lender default flag;
- approved amount cannot exceed current eligible guarantee exposure;
- settlement cannot occur twice;
- rejection preserves reason/evidence;
- claim lifecycle cannot silently increase guarantee exposure.

## 14. RecoveryCase Aggregate

### Root

**RecoveryCase**

### Owns

- Claim/Guarantee reference;
- recovery source;
- proceeds;
- enforcement costs;
- allocation method;
- lender/Badban shares;
- participant/program surplus;
- residual shortfall;
- closure state.

### Invariants

- only validly encumbered backing can enter collateral enforcement;
- recovery allocation follows captured contract/policy;
- surplus follows ownership policy;
- recovery cannot be double-applied.

## 15. ReturnAllocation Aggregate

### Root

**ReturnAllocationEvent**

### Owns

- source return reference;
- eligible net return;
- reserve allocation;
- livelihood allocation;
- future-financial allocation;
- capital-growth allocation;
- social-reinvestment allocation;
- carry-forward;
- profile/policy version;
- lifecycle state.

### Invariants

- allocations balance to source eligible return;
- principal cannot be used as return without explicit separate authority;
- posted event is immutable;
- correction uses reversal/adjustment.

## 16. FutureFinancialEntitlement Aggregate

### Root

**FutureFinancialEntitlement**

### Owns

- participant/episode;
- vested amount;
- unvested amount;
- paid amount;
- remaining amount;
- payout schedule;
- suspension/expiry state;
- policy reference.

### Invariants

- paid amount cannot exceed vested payable amount;
- projected return does not create entitlement;
- program principal is not silently consumed.

## 17. ExitCase Aggregate

### Root

**ParticipantExitCase**

### Owns

- ParticipationEpisode reference;
- exit lifecycle state;
- financial reconciliation checklist;
- releasable position references;
- restricted position references;
- future-financial state;
- unresolved obligations;
- finalization evidence.

### Invariants

- FINALIZED requires explicit classification of all rights/obligations;
- active guarantee does not disappear on program exit;
- participant-owned releasable assets cannot be silently recycled;
- program-attributed assets cannot be silently paid out.

## 18. LegalEntityAuthorization Aggregate

### Root

**LegalEntityAuthorization**

### Owns

- legal entity;
- regulated role;
- regulator/authority;
- authorization/license reference;
- scope;
- effective/expiry dates;
- status;
- evidence;
- review timestamp.

### Invariants

- invalid/expired authorization blocks new regulated action;
- historical transactions retain the authorization snapshot/reference used;
- provider partnership alone does not imply permission.

## 19. Journal Aggregate

### Root

**JournalEntry**

### Owns

- journal entry ID;
- business event reference;
- currency;
- postings;
- effective timestamp;
- posting timestamp;
- reversal linkage;
- actor/system;
- legal-entity dimensions.

### Invariants

- sum of monetary debits equals sum of monetary credits;
- posted entry immutable;
- reversal is separate entry;
- idempotency key unique within its posting scope;
- no direct balance mutation.

Balances are projections derived from posted journal entries.

## 20. ReconciliationCase Aggregate

### Root

**ReconciliationCase**

### Owns

- reconciliation type;
- internal reference;
- external reference;
- compared values/states;
- status;
- mismatch reason;
- evidence;
- resolution;
- reviewer.

### States

- PENDING;
- MATCHED;
- MISMATCH;
- STALE;
- DISPUTED;
- RESOLVED.

### Invariants

- resolution is auditable;
- material mismatches cannot be hidden by status overwrite;
- resolved mismatch retains original difference and resolution evidence.

## 21. AuditEvent

Audit events are append-only records rather than a business aggregate that users mutate.

Every high-impact command/state transition emits one.

Required fields:

- event ID;
- aggregate type/ID;
- actor;
- command/action;
- previous/new state;
- reason;
- correlation/causation IDs;
- policy version;
- evidence references;
- timestamp.

## 22. Cross-Aggregate Application Services

The following workflows are application-service orchestrations across aggregates.

### Reserve Guarantee Capacity

Coordinates:

- ParticipationEpisode;
- AssetPosition/BackingAllocation;
- Valuation;
- PolicyPack;
- PortfolioRisk;
- GuaranteeCase;
- Journal/Audit.

### Activate Guaranteed Loan

Coordinates:

- GuaranteeCase;
- LegalEntityAuthorization;
- ExternalLoanMirror;
- BackingAllocation;
- Journal;
- Audit.

### Process Repayment

Coordinates:

- ExternalLoanMirror;
- GuaranteeCase;
- BackingAllocation;
- Journal;
- Reconciliation;
- Audit.

### Process Claim

Coordinates:

- GuaranteeClaim;
- GuaranteeCase;
- Reserve;
- Journal;
- RecoveryCase;
- Audit.

### Finalize Exit

Coordinates:

- ParticipantExitCase;
- AssetPosition;
- GuaranteeCase;
- FutureFinancialEntitlement;
- ReconciliationCase;
- Journal;
- Audit.

## 23. Aggregate Anti-Patterns to Avoid

Do not create:

- one mega `Participant` aggregate containing all assets, loans, guarantees, balances, and claims;
- one mutable `balance` field standing in for ledger history;
- one generic `status` table shared by unrelated lifecycles;
- provider-specific aggregates that duplicate the generic provider/product/guarantee domains;
- a database transaction spanning external systems;
- an aggregate that treats external provider state as locally authorable.

## 24. Technical Consequence

The relational model may contain many tables, but service/module boundaries should follow these business aggregate responsibilities.

The next document specifies allowed lifecycle transitions and transition preconditions.
