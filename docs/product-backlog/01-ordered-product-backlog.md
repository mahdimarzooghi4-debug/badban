# Badban Ordered Product Backlog — Bounded External-Lender Pilot

- **Status:** Accepted
- **Date:** 2026-10-05
- **Stage:** Scrum/Product Backlog
- **Scope:** Decision 0016 bounded external-lender pilot
- **Entry Gate:** Decision 0018
- **Sprint / Code Authorization:** NOT YET GRANTED

## 1. Ordering Principle

The backlog is ordered to establish correctness and control foundations before business workflows that depend on them.

Priority order:

```
Architecture/runtime enablers
→ Identity / authorization
→ Core participant / asset / policy state
→ Deterministic valuation / capacity
→ Provider / legal-role registry
→ Guarantee reservation
→ Legal issuance + lender activation
→ Repayment / exposure release
→ Ledger / risk / reserve controls
→ Claims / recovery
→ Return allocation / entitlements / exit
→ Reconciliation / operational UIs
→ Security / observability / recovery hardening
→ End-to-end pilot readiness
```

Direct Lending is excluded.

---

## 2. P0 — Foundation and Correctness Prerequisites

### BL-001 — Implementation Stack Decision Pack

**Priority:** P0  
**Type:** Technical Enabler  
**Depends on:** Accepted Technical 00-15  
**Traceability:** Technical 14 §50; Decision 0018

**Goal**

Select the concrete implementation stack required for the first Sprint without weakening accepted Technical contracts.

**Scope**

Resolve and record:

- application language/framework;
- relational database product;
- migration tool;
- identity-provider implementation;
- secret/key manager;
- object/evidence storage;
- broker/queue decision, including justified "not initially required" if selected;
- observability stack;
- deployment platform;
- CI/CD toolchain.

**Acceptance Criteria**

- each selected component satisfies ACID/exact-decimal/idempotency/security/observability requirements;
- alternatives and rationale are recorded as repository decisions/ADRs;
- no selection introduces Direct Lending or changes accepted Business semantics;
- dependencies for local, CI, Stage, and Production-equivalent environments are explicit.

---

### BL-002 — Repository and CI Quality-Gate Blueprint

**Priority:** P0  
**Type:** Technical Enabler  
**Depends on:** BL-001  
**Traceability:** Technical 12, 13, 14

**Acceptance Criteria**

- required lint/type/test/security/migration checks are defined;
- CI must reject failed unit/domain/API/integration/security checks;
- build artifact must be traceable to source commit;
- secret scanning and dependency vulnerability scanning are included;
- no production deployment is implied by completion.

---

### BL-003 — Environment, Configuration, and Secret Boundary

**Priority:** P0  
**Type:** Technical Enabler  
**Depends on:** BL-001  
**Traceability:** Technical 12; Technical 14 §§10-12,25

**Acceptance Criteria**

- Dev/Test/Stage/Production configuration boundaries are defined;
- production secrets cannot be reused from Dev/Test;
- application configuration and secret references are separated;
- provider credentials are provider/environment scoped;
- local development does not require embedding production-like secrets in Git.

---

### BL-004 — Transactional Persistence and Migration Foundation

**Priority:** P0  
**Type:** Technical Enabler  
**Depends on:** BL-001  
**Traceability:** Technical 04; Technical 14 §§5,22

**Acceptance Criteria**

- exact decimal/numeric conventions are defined;
- aggregate versioning and optimistic concurrency conventions are defined;
- migration strategy follows expand/compatible/backfill/contract;
- append-only financial/history protections are implementable;
- transactional outbox/inbox can share the authoritative transaction boundary.

---

### BL-005 — Observability and Correlation Foundation

**Priority:** P0  
**Type:** Technical Enabler  
**Depends on:** BL-001, BL-003  
**Traceability:** Technical 13

**Acceptance Criteria**

- correlation/trace identifiers propagate through API/domain/worker/provider paths;
- structured logging fields are defined without secrets/PII leakage;
- metric and trace conventions support business-control indicators;
- liveness, readiness, and business-readiness are explicitly separate.

---

## 3. P0 — Identity, Authorization, and Governance

### BL-006 — Central Identity Integration

**Priority:** P0  
**Type:** Capability  
**Depends on:** BL-001, BL-003  
**Traceability:** Technical 01, 11, 12

**Acceptance Criteria**

- human identities authenticate through the selected OIDC/OAuth2 provider;
- privileged identities support MFA;
- service identities are distinct from human identities;
- provider identities cannot impersonate Badban users;
- session/token validation is environment-scoped and auditable.

---

### BL-007 — RBAC and Scoped Authorization Engine

**Priority:** P0  
**Type:** Capability  
**Depends on:** BL-006  
**Traceability:** Technical 11 §§8-14

**Acceptance Criteria**

- authorization is deny-by-default;
- role + program + legal entity + provider + resource scope can be enforced;
- read and write permissions are separate;
- participant access is self-scoped;
- cross-program/provider/entity access tests are defined.

---

### BL-008 — Maker-Checker / ApprovalRequest

**Priority:** P0  
**Type:** Capability  
**Depends on:** BL-007, BL-004  
**Traceability:** Technical 11 §§15-24

**Acceptance Criteria**

- ApprovalRequest state machine is represented;
- maker and checker identities must differ;
- approval binds to exact payload hash and target aggregate version;
- expired/changed approval cannot execute;
- approval never bypasses policy/legal/risk/reconciliation gates.

---

## 4. P1 — Program, Participant, Asset, and Valuation Foundation

### BL-009 — Program and Participation Episode

**Priority:** P1  
**Type:** Domain Capability  
**Depends on:** BL-004, BL-007  
**Traceability:** Technical 02, 03, 04, 07

**Acceptance Criteria**

- Program and ParticipationEpisode write models are explicit;
- participant/program scope is enforced;
- episode lifecycle supports later exit without equating exit to financial closure;
- audit/version fields are present.

---

### BL-010 — Asset Type Registry

**Priority:** P1  
**Type:** Domain Capability  
**Depends on:** BL-009  
**Traceability:** Decision 0001; Technical 02, 04

**Acceptance Criteria**

- Asset Type is configurable and not gold-hardcoded;
- unit, precision, valuation source reference, eligibility, custody/restriction metadata can be versioned;
- inactive/unapproved Asset Types cannot create new positions for pilot use;
- production Asset Type remains a later activation choice.

---

### BL-011 — Asset Position and Ownership/Funding Classification

**Priority:** P1  
**Type:** Domain Capability  
**Depends on:** BL-009, BL-010  
**Traceability:** Decision 0003; Technical 02, 04

**Acceptance Criteria**

- Asset Position distinguishes PARTICIPANT_OWNED and PROGRAM_ATTRIBUTED;
- quantity and ownership/custody references are explicit;
- market value and guarantee capacity are not stored as mutable asset balances;
- participant-owned and program-attributed rights remain distinguishable throughout the lifecycle.

---

### BL-012 — Immutable Valuation Observation

**Priority:** P1  
**Type:** Domain Capability  
**Depends on:** BL-010, BL-011  
**Traceability:** Decision 0008; Technical 04, 09

**Acceptance Criteria**

- accepted valuation observation is append-only/immutable;
- source, observed time, unit/quote basis, value, policy/source version, and evidence reference are captured;
- freshness is computable;
- stale valuation cannot create new guarantee capacity.

---

## 5. P1 — Policy Runtime and Deterministic Capacity

### BL-013 — Policy Version and Policy Pack Lifecycle

**Priority:** P1  
**Type:** Domain/Platform Capability  
**Depends on:** BL-004, BL-007, BL-008  
**Traceability:** Technical 06  
**Delivery Status:** Code + Code Review complete in Sprint 04; merged to `main`; Stage deferred by Decision 0023

**Acceptance Criteria**

- DRAFT → REVIEWED → APPROVED → ACTIVE → SUPERSEDED/RETIRED is enforced;
- approval and activation are separate;
- ACTIVE payload is immutable;
- exclusive scope activation prevents ambiguous double-active policy;
- activation produces audit and immutable manifest/hash.

---

### BL-014 — PolicyResolver and DecisionSnapshot

**Priority:** P1  
**Type:** Domain/Platform Capability  
**Depends on:** BL-013  
**Traceability:** Technical 06 §§5-9,21-24  
**Delivery Status:** Code + Code Review complete in Sprint 04; merged to `main`; Stage deferred by Decision 0023

**Acceptance Criteria**

- material commands resolve explicit policy version IDs;
- no financial decision uses implicit "latest policy";
- missing/ambiguous policy fails closed;
- decision snapshots capture inputs, outputs, policy versions, algorithm version, and evidence references;
- historical replay does not use fresh external facts.

---

### BL-015 — Deterministic Guarantee Capacity Calculator

**Priority:** P1  
**Type:** Domain Capability  
**Depends on:** BL-011, BL-012, BL-014  
**Traceability:** Decision 0008; Technical 06  
**Delivery Status:** Code + Code Review complete in Sprint 05; merged to `main`; Stage deferred by Decision 0023

**Acceptance Criteria**

Calculator implements the accepted architecture:

```
Gross Market Value
= Eligible Quantity × Approved Price × Approved FX Conversion

Pledgeable Market Value
= Gross Market Value × Pledgeable Fraction

Position Backing Capacity
= Pledgeable Market Value × Advance Rate

Available Guarantee Capacity
= max(
  0,
  Capped Gross Backing Capacity
  - Reserved Guarantee Capacity
  - Active Guarantee Exposure
  - Other Approved Capacity Holds
)
```

Additionally:

- exact decimal arithmetic only;
- rounding/version rules are explicit;
- stale valuation yields no new capacity;
- calculation result identifies policy/algorithm versions.

---

### BL-016 — Guarantee Capacity Read Model

**Priority:** P1  
**Type:** Query Capability  
**Depends on:** BL-015  
**Traceability:** Technical 07 §14  
**Delivery Status:** Code deferred by Decision 0030 until authoritative reservation/exposure/hold and portfolio-control sources exist; no synthetic zero/default values permitted

**Acceptance Criteria**

- returns gross/capped backing, reserved, active exposure, holds, and available capacity;
- returns valuation freshness, policy pack/version, calculation timestamp, algorithm version;
- read calculation alone never reserves capacity;
- participant/staff authorization scope is enforced.

---

## 6. P1 — Provider, Product, and Legal Authorization Registry

### BL-017 — Credit Provider and Product Version Registry

**Priority:** P1  
**Type:** Domain Capability  
**Depends on:** BL-013  
**Traceability:** Decisions 0005, 0011; Technical 02, 04, 09  
**Delivery Status:** Code + Code Review complete in Sprint 06; merged to `main`; Stage deferred by Decision 0023

**Acceptance Criteria**

- provider and product version are distinct;
- product terms are versioned and immutable once used by obligations;
- provider/product activation state is explicit;
- Direct Lending is absent/disabled for bounded pilot paths;
- pilot can restrict to one approved external lender/product without hard-coding names in core logic.

---

### BL-018 — Legal Entity Role and Authorization Registry

**Priority:** P1  
**Type:** Domain Capability  
**Depends on:** BL-007, BL-013  
**Traceability:** Decision 0014; Technical 01, 04, 11  
**Delivery Status:** Code + Code Review complete in Sprint 06; merged to `main`; Stage deferred by Decision 0023

**Acceptance Criteria**

- lender, Guarantee Issuer, custody/asset, settlement, and collateral-registry roles can be represented;
- authorization includes scope, validity, evidence, lifecycle state;
- missing/expired/suspended authorization fails closed;
- generic "Badban" identity is never treated as implicit regulated authority.

---

## 7. P1 — Guarantee Request, Reservation, and Backing Allocation

### BL-019 — Guarantee Request Aggregate Path

**Priority:** P1  
**Type:** Domain Capability  
**Depends on:** BL-009, BL-017, BL-018  
**Traceability:** Technical 02, 03, 07  
**Delivery Status:** Code + Code Review complete in Sprint 07; merged to `main`; Stage deferred by Decision 0023

**Acceptance Criteria**

- valid request creates GuaranteeCase in REQUESTED;
- requested principal is exact decimal;
- participant/program/provider/product references are explicit;
- no capacity is consumed merely by creating the request;
- API is idempotent and version-aware.

---

### BL-020 — Atomic Backing Reservation

**Priority:** P1  
**Type:** Financial-Control Capability  
**Depends on:** BL-015, BL-019, BL-004  
**Traceability:** Technical 03, 04, 07  
**Delivery Status:** Code deferred by Decision 0032 until BL-032 provides the required authoritative portfolio-risk PASS gate; no implicit/synthetic GREEN or PASS permitted

**Acceptance Criteria**

A reservation transaction atomically:

- resolves active policy;
- validates fresh valuation;
- validates participant capacity;
- validates provider/product/legal authorization;
- validates portfolio gate when available;
- locks/rechecks backing availability;
- creates exact BackingAllocation;
- moves GuaranteeCase to RESERVED;
- captures immutable DecisionSnapshot;
- writes audit/outbox;
- cannot double reserve under concurrency.

Failure leaves no partial reservation/control effect.

---

### BL-021 — Reservation Expiry

**Priority:** P1  
**Type:** Domain Capability  
**Depends on:** BL-020  
**Traceability:** Technical 03, 08, 14

**Acceptance Criteria**

- expiry runs through explicit idempotent command;
- expired reservation releases reserved backing exactly once;
- expiry emits audit/domain event;
- time passing never directly updates financial state in the database.

---

## 8. P1 — External Guarantee Issuance and Loan Activation

### BL-022 — Guarantee Issuer Adapter Baseline

**Priority:** P1  
**Type:** Integration Capability  
**Depends on:** BL-001, BL-003, BL-017, BL-018  
**Traceability:** Technical 09 §19

**Acceptance Criteria**

- provider-specific payload remains behind adapter;
- auth/secret handling follows Security contract;
- issue/query/normalize/reconciliation capability is defined;
- timeout/UNKNOWN_OUTCOME and idempotency behavior are explicit;
- legal issuance evidence can be preserved.

---

### BL-023 — Confirm Legal Guarantee Issuance

**Priority:** P1  
**Type:** Domain Capability  
**Depends on:** BL-020, BL-022  
**Traceability:** Technical 03, 07 §17

**Acceptance Criteria**

- only RESERVED and unexpired guarantee may become ISSUED;
- external guarantee ID, issuer, amount, timestamp, and evidence are required;
- legal authorization is VALID;
- issued amount equals reservation unless an explicit valid amendment exists;
- internal reservation alone can never be treated as legal issuance.

---

### BL-024 — Lender Adapter Baseline

**Priority:** P1  
**Type:** Integration Capability  
**Depends on:** BL-001, BL-003, BL-017, BL-018  
**Traceability:** Technical 09 §18  
**Delivery Status:** Selected for Sprint 13; Code authorized by Decision 0038

**Acceptance Criteria**

- lender auth/secret boundary is implemented by adapter contract;
- normalized events include approval/disbursement/repayment/delinquency/settlement/correction;
- external IDs and exact decimal principal/outstanding values are preserved;
- duplicate events are detectable;
- reconciliation snapshot path exists.

---

### BL-025 — External Loan Mirror

**Priority:** P1  
**Type:** Domain Capability  
**Depends on:** BL-024, BL-004  
**Traceability:** Technical 02, 03, 04  
**Delivery Status:** Selected for Sprint 13 after BL-024 within the same authorized Sprint

**Acceptance Criteria**

- lender is explicit lender of record;
- provider + external loan ID is unique;
- original and outstanding principal use exact decimals;
- provider-authoritative state changes are applied only from authenticated normalized facts;
- historical/correction events remain auditable.

---

### BL-026 — Activate Guaranteed External Loan

**Priority:** P1  
**Type:** Golden-Path Capability  
**Depends on:** BL-023, BL-024, BL-025, BL-020  
**Traceability:** Decision 0009; Technical 03, 07 §18, 08 §19

**Acceptance Criteria**

Activation requires:

- GuaranteeCase state ISSUED;
- authoritative lender disbursement evidence;
- external loan ID;
- valid legal/provider state;
- no blocking reconciliation condition;
- exact invariant:
  `External Loan Principal = Issued Guarantee Amount`.

On success:

- external loan mirror becomes ACTIVE;
- reserved backing becomes ENCUMBERED;
- guarantee becomes ACTIVE;
- decision/audit/outbox records are produced atomically.

Mismatch returns `LOAN_GUARANTEE_AMOUNT_MISMATCH` with no partial activation.

---

## 9. P2 — Repayment, Exposure Reduction, and Release

### BL-027 — Process Lender Repayment

**Priority:** P2  
**Type:** Domain/Integration Capability  
**Depends on:** BL-025, BL-026  
**Traceability:** Technical 03, 08 §20

**Acceptance Criteria**

- provider event is inbox-deduplicated;
- outstanding principal reduces exactly once;
- duplicate callback cannot duplicate repayment effect;
- correction/reversal uses explicit provider/domain correction path;
- no Badban cash journal is created merely because lender received repayment.

---

### BL-028 — Declining Guarantee Exposure Reduction

**Priority:** P2  
**Type:** Financial-Control Capability  
**Depends on:** BL-027  
**Traceability:** Technical 03, 05

**Acceptance Criteria**

- only authoritative eligible repayment can reduce declining exposure;
- fixed guarantee mode does not reduce unless captured rule permits;
- released backing matches approved exposure-reduction rule;
- control/memorandum records remain balanced/traceable;
- product/guarantee captured rule version is used, not current latest policy.

---

### BL-029 — Loan Settlement / Guarantee Release / Closure

**Priority:** P2  
**Type:** Domain Capability  
**Depends on:** BL-027, BL-028  
**Traceability:** Technical 03

**Acceptance Criteria**

- RELEASED/CLOSED requires authoritative repayment/settlement evidence;
- remaining exposure is zero as required;
- backing release is complete;
- no unresolved claim or blocking reconciliation remains;
- closure never relies only on UI/read-model state.

---

## 10. P1/P2 — Ledger, Risk, and Reserve

### BL-030 — Append-Only Journal Engine

**Priority:** P1  
**Type:** Financial Platform Capability  
**Depends on:** BL-004, BL-007  
**Traceability:** Decision 0015; Technical 05  
**Delivery Status:** Code + Code Review complete in Sprint 08; merged to `main` as PR #10; post-merge CI #218 green; Stage is separately governed by Decision 0033

**Acceptance Criteria**

- every POSTED journal balances exactly;
- balances are derived from postings;
- posted journal rows are immutable;
- corrections use linked reversal/adjustment;
- legal entity/economic owner dimensions are explicit;
- direct arbitrary balance mutation is impossible through normal API.

---

### BL-031 — Product Account Taxonomy and Posting Templates

**Priority:** P2  
**Type:** Financial Platform Capability  
**Depends on:** BL-030  
**Traceability:** Technical 05  
**Delivery Status:** Code + Code Review complete in Sprint 10; merged to `main` as PR #12; post-merge CI #249 green

**Acceptance Criteria**

- monetary, memorandum/control, and external-mirror semantics remain distinct;
- reservation/issuance/activation do not invent Badban cash/loan receivable;
- claim payment remains pending recovery before final residual loss determination;
- return allocation preserves ownership/entitlement buckets;
- historical template/version mapping is retained.

---

### BL-032 — Portfolio Risk Snapshot and Gate

**Priority:** P1  
**Type:** Risk Capability  
**Depends on:** BL-013, BL-015, BL-030  
**Traceability:** Decision 0010; Technical 02, 04, 07  
**Delivery Status:** Code + Code Review complete in Sprint 09; merged to `main` as PR #11; post-merge CI #232 green

**Acceptance Criteria**

- immutable risk snapshots produce GREEN/AMBER/RED;
- snapshot identifies policy version and evaluated inputs;
- RED blocks new exposure;
- existing obligations are not silently rewritten by new risk state;
- reservation uses a captured risk snapshot.

---

### BL-033 — Guarantee Reserve Control

**Priority:** P2  
**Type:** Financial/Risk Capability  
**Depends on:** BL-030, BL-032  
**Traceability:** Decisions 0007, 0010; Technical 05

**Acceptance Criteria**

- reserve designated balance and reserve cash/control balance are separate;
- participant-owned collateral is never treated as general reserve;
- reserve draw/replenishment is journaled and auditable;
- cash completion requires external settlement evidence when applicable.

---

## 11. P2 — Delinquency, Claim, Recovery, and Loss

### BL-034 — Delinquency Processing

**Priority:** P2  
**Type:** Domain/Integration Capability  
**Depends on:** BL-025, BL-024  
**Traceability:** Technical 03, 08

**Acceptance Criteria**

- delinquency originates from authoritative lender fact;
- duplicate/out-of-order events cannot regress state;
- GuaranteeCase enters DELINQUENT through explicit transition;
- reconciliation state remains visible.

---

### BL-035 — Claim Submission and Review

**Priority:** P2  
**Type:** Domain Capability  
**Depends on:** BL-034, BL-008, BL-032  
**Traceability:** Decision 0007; Technical 03, 07

**Acceptance Criteria**

- claim reference and evidence are immutable/auditable;
- eligible amount cannot exceed guarantee exposure;
- duplicate claim reference is rejected/deduplicated;
- review/approve/reject transitions are explicit;
- maker-checker is applied according to approved policy.

---

### BL-036 — Claim Settlement

**Priority:** P2  
**Type:** Financial Capability  
**Depends on:** BL-035, BL-030, BL-033  
**Traceability:** Technical 05 §§17-18

**Acceptance Criteria**

- settlement cannot occur before APPROVED;
- external settlement evidence is required before PAID;
- reserve/cash posting uses accepted templates;
- claim payment does not immediately become final residual loss;
- RecoveryCase opens as required.

---

### BL-037 — Recovery Receipts and Allocation

**Priority:** P2  
**Type:** Financial Capability  
**Depends on:** BL-036, BL-030  
**Traceability:** Decision 0007; Technical 05 §§19-21

**Acceptance Criteria**

- recovery receipts are idempotent;
- collateral/cash evidence is preserved;
- recovery allocation follows accepted waterfall and ownership;
- surplus is not default Badban corporate income;
- final residual loss is posted only after recovery determination/closure conditions.

---

## 12. P2 — Return Allocation, Entitlements, and Exit

### BL-038 — Return Recognition and Allocation

**Priority:** P2  
**Type:** Financial Capability  
**Depends on:** BL-030, BL-013  
**Traceability:** Decision 0012; Technical 05 §§11-13

**Acceptance Criteria**

- only recognized economic return enters allocation;
- principal is not distributable return;
- allocation equation balances exactly;
- reserve/livelihood/future-financial/capital-growth/social/carry-forward buckets are versioned;
- participant/program ownership drives capital-growth destination.

---

### BL-039 — Future Financial Entitlement

**Priority:** P2  
**Type:** Financial Capability  
**Depends on:** BL-038  
**Traceability:** Decisions 0012, 0013; Technical 04, 05

**Acceptance Criteria**

- entitlement and payment are separate;
- payment cannot exceed vested payable balance;
- real payment requires settlement evidence;
- participant-visible balance can be derived from journal/sub-ledger truth.

---

### BL-040 — Participant Exit and Financial Reconciliation

**Priority:** P2  
**Type:** Domain/Financial Capability  
**Depends on:** BL-009, BL-029, BL-037, BL-039  
**Traceability:** Decision 0013; Technical 03, 10

**Acceptance Criteria**

- Program Exit remains distinct from Financial Closure;
- participant-owned and program-attributed positions receive different treatment;
- active obligations survive program exit when required;
- finalization is blocked by unresolved required obligations/reconciliation;
- recyclable program capital and participant release payable remain distinct.

---

## 13. P1/P2 — Eventing, Reconciliation, and Audit

### BL-041 — Transactional Outbox / Inbox

**Priority:** P1  
**Type:** Integration Platform Capability  
**Depends on:** BL-004  
**Traceability:** Technical 08  
**Delivery Status:** Code + Code Review complete in Sprint 11; merged to `main` as PR #13; post-merge CI #258 green

**Acceptance Criteria**

- domain state and outbox event commit in the same transaction;
- provider inbox deduplicates provider+type+external ID;
- at-least-once delivery yields exactly-once business effect;
- crashes/retries do not duplicate financial state;
- dead-letter/replay is explicit and auditable.

---

### BL-042 — Reconciliation Engine Core

**Priority:** P1  
**Type:** Control Capability  
**Depends on:** BL-024, BL-025, BL-030, BL-041  
**Traceability:** Technical 10
**Delivery Status:** Selected for Sprint 14; Decision 0039; Code/CI/Review pending

**Acceptance Criteria**

- supports lender, guarantee issuer, custody/asset, settlement, collateral registry, and internal ledger/sub-ledger reconciliation;
- source cutoffs/evidence are recorded;
- MATCHED, MISMATCH, STALE, DISPUTED, RESOLVED are explicit;
- stale source is never treated as matched;
- one-to-one loan/guarantee mismatch is CRITICAL.

---

### BL-043 — Reconciliation Blocks and Resolution Workflow

**Priority:** P2  
**Type:** Control Capability  
**Depends on:** BL-042, BL-008  
**Traceability:** Technical 10 §§10,24-29

**Acceptance Criteria**

- unresolved MATERIAL/CRITICAL cases can activate command blocks;
- block policy identifies affected command/resource;
- resolution requires evidence and approved resolution type;
- material/critical resolution supports maker-checker;
- repair uses normal domain command/reversal paths, not direct row edits.

---

### BL-044 — Audit and Evidence Trace

**Priority:** P1  
**Type:** Control Capability  
**Depends on:** BL-004, BL-006  
**Traceability:** Technical 01, 04, 12  
**Delivery Status:** Code + Code Review complete in Sprint 12; merged to `main` as PR #14; post-merge CI #271 green

**Acceptance Criteria**

- material commands record actor/system, correlation, policy/evidence references, and outcome;
- audit records are append-only/protected;
- evidence references are opaque and access-controlled;
- secrets/raw restricted content are not copied into generic audit/log payloads.

---

## 14. P2 — Operational and Participant Read Models / UI

### BL-045 — Guarantee Operations Workspace

**Priority:** P2  
**Type:** Read Model / UI Capability  
**Depends on:** BL-026, BL-027, BL-035, BL-042  
**Traceability:** Technical 07 §19

**Acceptance Criteria**

Workspace exposes authorized current state for:

- guarantee lifecycle;
- provider/product;
- backing allocations;
- policy/valuation snapshots;
- external loan;
- reconciliation blockers;
- claims/recovery;
- currently permitted actions for actor.

No UI action bypasses command authorization/business gates.

---

### BL-046 — Finance / Reconciliation Operations Workspace

**Priority:** P2  
**Type:** Read Model / UI Capability  
**Depends on:** BL-030, BL-042, BL-043  
**Traceability:** Technical 07 §§27-28; Technical 13

**Acceptance Criteria**

- reconciliation queue exposes materiality/freshness/provider/age;
- finance can inspect journals without arbitrary edit capability;
- reversal/resolution actions route through approved maker-checker/domain commands;
- stale/critical conditions are explicit.

---

### BL-047 — Participant Badban Summary

**Priority:** P2  
**Type:** Read Model / UI Capability  
**Depends on:** BL-016, BL-025, BL-039, BL-040  
**Traceability:** Technical 07 §32

**Acceptance Criteria**

Participant can view authorized self-scoped summary of:

- participant-owned vs program-attributed assets;
- valuation freshness;
- available/encumbered backing;
- guarantee status;
- lender identity and external outstanding state;
- entitlement/release status.

Internal risk secrets and unrelated records are not exposed.

---

## 15. P3 — Security, Reliability, and Operational Hardening

### BL-048 — Security Hardening and Secret Rotation Verification

**Priority:** P3  
**Type:** Security Enabler  
**Depends on:** BL-003, BL-006, provider adapters  
**Traceability:** Technical 12

**Acceptance Criteria**

- no raw secrets in source/logs/browser/ordinary DB;
- rotation is tested for selected provider/system credentials;
- webhook replay/signature failure paths are tested;
- production/non-production credential separation is verifiable;
- privileged access/break-glass path is audited.

---

### BL-049 — Business Readiness / Stop Controls

**Priority:** P3  
**Type:** Operational Capability  
**Depends on:** BL-032, BL-042, BL-005  
**Traceability:** Technical 13 §§7,29

**Acceptance Criteria**

- liveness/readiness/business-readiness are distinct;
- safe stop controls can restrict reservation, activation, provider use, claim settlement, and collateral release;
- stop controls do not mutate existing obligations;
- every change is audited.

---

### BL-050 — Backup / Restore / Recovery Verification

**Priority:** P3  
**Type:** Operational Enabler  
**Depends on:** BL-004, BL-041, BL-042  
**Traceability:** Technical 12 §§29-30; Technical 13 §§30-31; Technical 14 §§18-20

**Acceptance Criteria**

Restore rehearsal verifies:

- database integrity;
- journal balance;
- aggregate versions;
- outbox/inbox consistency;
- evidence references;
- access controls;
- reconciliation can be re-established.

A process restart alone is not considered recovery.

---

### BL-051 — Concurrency, Retry, and Failure-Injection Suite

**Priority:** P3  
**Type:** Test Enabler  
**Depends on:** BL-020, BL-026, BL-030, BL-041  
**Traceability:** Technical 04, 08, 14

**Acceptance Criteria**

Automated tests prove:

- no double reservation under concurrency;
- no duplicate repayment/claim/payment effect;
- worker crash/retry safety;
- broker redelivery safety;
- provider timeout/UNKNOWN_OUTCOME safety;
- failed financial transactions leave no partial effects.

---

### BL-052 — Bounded Pilot End-to-End Golden Path

**Priority:** P1 for Release Candidate / P3 dependency depth  
**Type:** End-to-End Acceptance Capability  
**Depends on:** BL-009 through BL-051 as applicable  
**Traceability:** Business completion review; Technical 14 §43

**Acceptance Criteria**

A controlled non-real-money environment can execute and prove:

```
Participant / Program
→ Asset Position
→ Accepted Valuation
→ Active Policy Pack
→ Capacity
→ Guarantee Request
→ Reservation
→ Legal Guarantee Issuance
→ External Lender Disbursement
→ Exact 1:1 Activation
→ Repayment
→ Exposure / Backing Release
→ Closure
→ Reconciliation / Audit
```

And a separate controlled exception path proves:

```
Delinquency
→ Claim
→ Settlement
→ Recovery
→ Residual Loss / Closure
```

All critical states, policy snapshots, provider evidence, ledger/control effects, authorization, events, and reconciliation remain traceable.

---

## 16. Future / Explicitly Deferred

### FUT-001 — Badban Direct Lending

**Status:** Deferred / Outside Pilot  
**Traceability:** Decisions 0004, 0014, 0016

No Direct Lending code may be pulled into the bounded-pilot Sprint unless the Business/legal stage is reopened and required decisions/gates are accepted.

---

## 17. Ordered First-Pass Backlog

The current first-pass order is:

```
BL-001 → BL-002 → BL-003 → BL-004 → BL-005
→ BL-006 → BL-007 → BL-008
→ BL-009 → BL-010 → BL-011 → BL-012
→ BL-013 → BL-014 → BL-015 → BL-016
→ BL-017 → BL-018
→ BL-019 → BL-020 → BL-021
→ BL-022 → BL-023 → BL-024 → BL-025 → BL-026
→ BL-041 → BL-044
→ BL-030 → BL-032
→ BL-027 → BL-028 → BL-029
→ BL-031 → BL-033
→ BL-034 → BL-035 → BL-036 → BL-037
→ BL-038 → BL-039 → BL-040
→ BL-042 → BL-043
→ BL-045 → BL-046 → BL-047
→ BL-048 → BL-049 → BL-050 → BL-051
→ BL-052
```

This ordering is dependency-oriented, not an instruction that every item must occupy a separate Sprint.

## 18. Product-Backlog Exit Condition

Before authorizing Sprint planning, this backlog must be reviewed together with:

- Definition of Ready / Done;
- delivery slices/dependency plan;
- required stack decisions for the first Sprint.

No Code is authorized by this document.
