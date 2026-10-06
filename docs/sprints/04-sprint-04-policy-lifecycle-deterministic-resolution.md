# Sprint 04 — Policy Lifecycle and Deterministic Resolution

- **Status:** Completed through Code Review; Merged to main
- **Date:** 2026-10-06
- **Stage:** Deferred by Decision 0023
- **Scope:** bounded external-lender pilot
- **Entry Gate:** Decision 0023; Decision 0027
- **Depends on:** Sprint 03 Code + Code Review Complete
- **Code Authorization:** GRANTED BY DECISION 0028

## 1. Sprint Goal

Deliver the policy runtime foundation required before any guarantee-capacity calculation is allowed.

Sprint 04 is intentionally small and contains only:

- **BL-013 — Policy Version and Policy Pack Lifecycle**
- **BL-014 — PolicyResolver and DecisionSnapshot**

The Sprint must make policy selection explicit, versioned, reproducible, fail-closed, and auditable without implementing guarantee-capacity mathematics yet.

## 2. Why This Scope Is Small

The remaining candidate Slice 2 items are now dependency-reachable, but they are intentionally not all taken together.

Sprint 04 stops at deterministic policy resolution.

The following remain for later Sprint(s):

- BL-015 Deterministic Guarantee Capacity Calculator;
- BL-016 Guarantee Capacity Read Model;
- BL-032 Portfolio Risk Snapshot and Gate.

This keeps the increment small and lets the policy runtime be reviewed independently before it becomes an input to financial/risk calculations.

## 3. Dependency Order

```
BL-008 Maker-Checker ✓
BL-012 Immutable Valuation ✓
BL-030 Journal Engine ✓
        │
        └─→ BL-013 Policy Lifecycle
                │
                └─→ BL-014 PolicyResolver + DecisionSnapshot
```

BL-013 must be functionally complete before BL-014 can resolve ACTIVE policy versions.

## 4. BL-013 — Policy Version and Policy Pack Lifecycle

Implement versioned policy records for the Accepted Technical 06 policy categories, including the Pilot Policy Pack.

The runtime must support the lifecycle:

```
DRAFT
→ REVIEWED
→ APPROVED
→ ACTIVE
→ SUPERSEDED / RETIRED
```

### Hard Rules

- approval does not automatically activate;
- activation is a distinct explicit command;
- only ACTIVE policy may authorize new pilot decisions;
- ACTIVE payload is immutable;
- SUPERSEDED/RETIRED versions remain readable;
- no lifecycle command may silently rewrite historical policy;
- canonical payload hash is stored for APPROVED/ACTIVE content;
- invalid lifecycle transitions fail closed;
- concurrent activation cannot produce two incompatible ACTIVE policies for an exclusive scope;
- activation of a new compatible exclusive-scope version atomically supersedes the prior ACTIVE version;
- every lifecycle transition is audited;
- high-impact policy changes must use the existing ApprovalRequest/maker-checker foundation according to the Accepted impact rules;
- no self-approval bypass is introduced.

## 5. Policy Pack

A Pilot Policy Pack is an immutable manifest of exact component version IDs.

It must not contain mutable "latest" pointers.

The pack may reference component versions for accepted categories such as:

- Asset Type Policy;
- Ownership/Funding Policy;
- Provider/Product Policy;
- Risk Appetite Policy;
- Return Allocation Policy;
- Legal/Authorization Policy;
- Posting/Accounting Mapping Policy.

Sprint 04 must not invent production numeric policy values.

Test fixtures may use clearly synthetic values only to prove versioning, validation, hashing, activation, and resolution behavior.

## 6. Scope and Effective-Time Model

Policy resolution input may include the Accepted context dimensions:

- effective timestamp;
- program;
- participation episode;
- Asset Type;
- ownership/funding type;
- provider;
- credit product;
- legal role/entity;
- transaction type;
- pilot scope.

Policy versions must persist explicit scope definitions and effective windows.

The implementation must not introduce an undocumented fallback hierarchy.

If more than one incompatible ACTIVE policy matches the same exclusive context:

`POLICY_SCOPE_AMBIGUOUS`

If no required policy matches:

`POLICY_SCOPE_NOT_FOUND`

## 7. BL-014 — PolicyResolver

Implement a deterministic PolicyResolver that:

- receives an explicit context;
- resolves the ACTIVE Pilot Policy Pack for that context/effective time;
- resolves exact component version IDs;
- validates that referenced component versions exist and are compatible;
- returns an immutable resolved manifest;
- never performs guarantee-capacity or other domain calculations.

### Forbidden Runtime Pattern

Material commands must not call an implicit:

`getLatestPolicy()`

The resolver returns exact IDs that downstream commands must persist/use explicitly.

## 8. DecisionSnapshot Baseline

Implement append-only DecisionSnapshot persistence and an internal application service for future material decisions.

Capture at minimum:

- business entity type/id;
- decision type;
- Policy Pack ID/version;
- exact relevant component version IDs;
- algorithm code;
- algorithm version;
- material input payload;
- material output payload;
- input hash;
- output hash;
- valuation observation IDs when supplied;
- authoritative external references when supplied;
- risk snapshot ID when supplied;
- effective timestamp;
- actor/system;
- created timestamp.

### Hard Rules

- snapshots are append-only;
- historical replay uses captured inputs/version IDs;
- replay must not fetch fresh external facts to reconstruct the old decision;
- policy version and algorithm version are separate;
- a later ACTIVE policy never rewrites an existing snapshot.

Sprint 04 may provide an internal snapshot-writing service and authorized read/query path.

A generic public API allowing arbitrary clients to forge authoritative DecisionSnapshots is prohibited.

## 9. Policy Validation

Before APPROVED/ACTIVE, structural validation must run.

Sprint 04 should validate structure and references that are already defined by accepted contracts, without inventing final Pilot numeric values.

Examples include:

- required manifest component references exist;
- referenced versions are in a lifecycle state permitted by the operation;
- scope definition is well-formed;
- effective window is valid;
- payload schema/version is recognized;
- pack references exact immutable IDs;
- incompatible/missing required component references fail closed.

Stable failure code:

`POLICY_VALIDATION_FAILED`

## 10. Activation Conflict and Concurrency

Exclusive-scope activation must be transactional.

The implementation must prove:

1. scope is locked or equivalently protected;
2. an incompatible double-ACTIVE result cannot commit;
3. previous ACTIVE version is SUPERSEDED atomically when appropriate;
4. new version becomes ACTIVE;
5. audit/outbox evidence is recorded in the same business transaction where required;
6. cache, if any, is never authoritative.

Sprint 04 does not require introducing a policy cache.

If no safe resolution is possible:

`POLICY_RESOLUTION_UNAVAILABLE`

## 11. Expected Persistence

Expected additions include:

- `policy_versions`;
- `decision_snapshots`;
- any normalized policy-pack component-reference structure needed to enforce exact version references;
- uniqueness/index/constraint support for lifecycle, version number, scope, and exclusive activation.

The design must preserve:

- immutable APPROVED/ACTIVE payload hashes;
- immutable ACTIVE content;
- append-only DecisionSnapshots;
- historical readability.

## 12. Proposed API / Service Surface

Logical policy commands may include:

```
POST /api/v1/policies
GET  /api/v1/policies/{id}

POST /api/v1/policies/{id}/review
POST /api/v1/policies/{id}/approve
POST /api/v1/policies/{id}/activate
POST /api/v1/policies/{id}/retire
```

Logical resolver/read operations may include:

```
POST /api/v1/policy-resolution
GET  /api/v1/decision-snapshots/{id}
```

Exact endpoint naming may be refined during implementation while preserving the Accepted command/query contract.

No endpoint named or behaving as implicit "latest policy" is permitted for material decisions.

## 13. Authorization

At minimum:

- lifecycle writes require explicit authorized governance/risk/legal/finance role according to policy category and scope;
- high-impact approval/activation uses maker-checker where required by Accepted policy impact rules;
- AUDITOR may read authorized historical policy/snapshot data but cannot mutate policy;
- cross-scope policy mutation is denied;
- server-authenticated actor identity is authoritative.

No universal admin bypass is introduced.

## 14. Acceptance Tests — Lifecycle

Must prove:

- DRAFT creation succeeds for authorized actor;
- invalid transition fails;
- REVIEWED does not imply APPROVED;
- APPROVED does not imply ACTIVE;
- ACTIVE content cannot be mutated;
- explicit activation succeeds only from allowed state;
- concurrent exclusive-scope activation cannot leave double ACTIVE;
- activating replacement supersedes prior ACTIVE atomically;
- retired/superseded versions remain readable;
- canonical payload hash is stable;
- changed payload changes hash;
- unauthorized/cross-scope mutation is denied;
- high-impact flow cannot self-approve where maker-checker is required.

## 15. Acceptance Tests — Resolver

Must prove:

- exact ACTIVE pack resolves for matching context/effective time;
- resolver returns exact component version IDs;
- missing scope fails with `POLICY_SCOPE_NOT_FOUND`;
- ambiguous match fails with `POLICY_SCOPE_AMBIGUOUS`;
- inactive pack cannot authorize resolution;
- missing component fails with `POLICY_COMPONENT_MISSING`;
- incompatible component fails closed;
- no implicit latest-policy behavior exists;
- same stored policy state + same context resolves identically.

## 16. Acceptance Tests — DecisionSnapshot

Must prove:

- snapshot stores explicit policy/algorithm version references;
- input/output hashes are reproducible;
- snapshot cannot be UPDATEd or DELETEd through normal/runtime persistence path;
- later policy activation does not alter historical snapshot;
- replay reads captured inputs instead of performing fresh external lookups;
- DecisionSnapshot creation does not itself reserve capacity, create guarantee exposure, or post money.

## 17. Definition of Done

Sprint 04 is Done only when:

- its Code authorization is separately Accepted;
- migrations apply from current `main`;
- migration drift check is green;
- lifecycle/state-machine tests are green;
- maker-checker integration tests are green where required;
- activation concurrency tests are green;
- PolicyResolver ambiguity/missing/inactive tests are green;
- DecisionSnapshot immutability/replay tests are green;
- format/lint/type/security/dependency/container CI gates are green;
- no capacity/risk/provider/guarantee/lending behavior is prematurely implemented;
- Code Review completes.

## 18. Explicit Non-Goals

Sprint 04 must not implement:

- BL-015 Guarantee Capacity Calculator;
- BL-016 Guarantee Capacity Read Model;
- BL-032 Portfolio Risk Snapshot/Gate;
- Provider/Product Registry;
- Legal Entity Authorization Registry;
- guarantee request/reservation/issuance;
- lender integration;
- external loan mirror;
- claim/recovery;
- return allocation;
- Direct Lending;
- real-money policy values;
- Stage;
- QA/Release Approval;
- Production.

## 19. Stage Deferral

Decision 0023 remains in force.

If later authorized and implemented, Sprint 04 output will join the accumulated future Stage candidate. It will not satisfy or bypass Stage.

## 20. Approval Effect

This Sprint 04 plan is **Accepted**.

Decision 0028 grants Code authorization only for BL-013 and BL-014.


## 21. Completion Record

Sprint 04 completed its authorized Code and Code Review scope for BL-013 and BL-014.

- Pull Request: #5 — `Sprint 04: policy lifecycle persistence foundation`
- Reviewed head: `7892b8f4aa56c842ddc26ae251d37149032bbedb`
- Reviewed-head CI: Run #159 — SUCCESS
- Merge commit on `main`: `36eb5656a9417a1da6586b3caa9f006d0efb4792`
- BL-013: Code + Code Review complete
- BL-014: Code + Code Review complete
- Stage: Deferred under Decision 0023
- QA/Testing gate completion: not claimed
- Release Approval: not claimed
- Production / real-money use: not authorized

No BL-015, BL-016, BL-032, Provider/Product Registry, Legal Entity Authorization Registry, guarantee flow, lending integration, claims/recovery, return allocation, or Direct Lending work is authorized by this completion record.
