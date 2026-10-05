# Badban Policy and Versioning Runtime Model

- **Status:** Proposed
- **Date:** 2026-10-05
- **Stage:** Technical
- **Scope:** bounded external-lender pilot
- **Depends on:** Technical Foundation; State Machines; Relational Data Model; Ledger Posting Model; Decisions 0008, 0010, 0011, 0012, 0016

## 1. Objective

Badban must make every material financial and risk decision reproducible from immutable inputs and explicit policy versions.

Core rule:

```
Same captured inputs
+ Same algorithm version
+ Same policy versions
= Same decision
```

Historical transactions must never be silently re-evaluated using today's policy.

## 2. Versioned Policy Categories

The runtime model supports explicit versions for:

- Asset Type Policy;
- Ownership/Funding Policy;
- Provider/Product Policy;
- Risk Appetite Policy;
- Return Allocation Policy;
- Legal/Authorization Policy;
- Posting/Accounting Mapping Policy;
- Pilot Policy Pack.

## 3. Pilot Policy Pack

A Pilot Policy Pack is an immutable manifest of exact component versions.

Example:

```
PilotPolicyPack v7
  ├─ AssetTypePolicy GOLD v3
  ├─ OwnershipPolicy PROGRAM_ATTRIBUTED v2
  ├─ CreditProduct BANK_A_PRODUCT_1 v5
  ├─ RiskPolicy PILOT_RISK v4
  ├─ ReturnAllocationPolicy BASE_SUPPORT v2
  ├─ LegalRolePolicy v6
  └─ PostingTemplateSet v3
```

The pack stores version IDs, not mutable "latest" pointers.

## 4. Lifecycle

Each version follows:

```
DRAFT
→ REVIEWED
→ APPROVED
→ ACTIVE
→ SUPERSEDED / RETIRED
```

Rules:

- only ACTIVE authorizes new real pilot transactions;
- approval does not automatically activate;
- ACTIVE content is immutable;
- superseded/retired versions remain readable for replay;
- activation is explicit and audited.

## 5. Scope Resolution

Policy resolution input includes:

- effective timestamp;
- program;
- participation episode;
- Asset Type;
- ownership/funding type;
- provider;
- credit product;
- legal roles/entities;
- transaction type;
- pilot scope.

Resolution returns exact version IDs.

If multiple versions match ambiguously, fail with:

`POLICY_SCOPE_AMBIGUOUS`

If none match, fail with:

`POLICY_SCOPE_NOT_FOUND`

No arbitrary fallback is allowed.

## 6. No Implicit Latest Policy

Material commands must not call an implicit `getLatestPolicy()`.

The application service resolves the pack once and passes explicit IDs into the command.

Example:

```
ReserveGuaranteeCapacity(
  policy_pack_id = P7,
  asset_policy_version_id = A3,
  risk_policy_version_id = R4,
  credit_product_version_id = C5
)
```

## 7. Decision Snapshot

Every material decision stores an immutable snapshot containing:

- policy pack ID/version;
- relevant component version IDs;
- algorithm code/version;
- material numeric inputs;
- valuation observation IDs;
- external authoritative references;
- risk snapshot ID where applicable;
- calculation output;
- effective timestamp;
- actor/system.

Required for at least:

- guarantee capacity;
- reservation;
- issuance/activation;
- claim approval;
- reserve evaluation;
- return allocation;
- exit entitlement calculation.

## 8. Algorithm Version

Policy version and code algorithm version are separate.

Example:

```
capacity_algorithm = CAPACITY_V1
asset_policy = GOLD_V3
```

If code later changes materially to `CAPACITY_V2`, historical replay must still use V1 semantics.

## 9. Reservation Snapshot

When GuaranteeCase becomes RESERVED, capture:

- active Pilot Policy Pack;
- Asset Type Policy;
- Ownership Policy;
- valuation observation IDs;
- capacity algorithm version;
- Risk Policy and risk snapshot;
- provider/product version;
- reservation validity rule;
- rounding rule;
- requested/reserved amount.

This snapshot is immutable.

## 10. Issuance and Activation

A newer policy becoming ACTIVE after reservation must not silently rewrite reserved terms.

At issuance or activation, the system may:

- continue under captured policy;
- reject and require a new reservation;
- apply an explicit approved amendment.

It must never silently migrate the transaction.

The hard invariant remains:

```
External Loan Principal = Issued Guarantee Amount
```

## 11. Repayment and Exposure Reduction

For DECLINING guarantees, repayment-driven exposure reduction uses the product rule captured for that obligation.

A later product policy does not retroactively change active repayment/release behavior.

## 12. Claim Policy

Claim eligibility uses:

- issued guarantee terms snapshot;
- captured product/delinquency/claim rules;
- current authoritative loan facts;
- claim evidence.

Current policy may restrict operations, but cannot silently rewrite contractual guarantee terms.

## 13. Return Allocation Policy

Every ReturnAllocationEvent captures:

- source return;
- allocation profile;
- allocation policy version;
- ownership policy version;
- risk/reserve policy version;
- exact allocation rules;
- rounding rule;
- algorithm version.

POSTED allocation events never change when a later policy becomes ACTIVE.

## 14. Policy Validation

Before APPROVED/ACTIVE, validate structure and cross-component compatibility.

Examples:

- Advance Rate in `[0,1]`;
- valuation source configured;
- product max >= min;
- tenor/repayment rules complete;
- risk thresholds internally consistent;
- return-allocation bounds valid;
- provider/product/Asset Type scopes compatible;
- legal authorization covers selected role;
- posting templates support required ownership dimensions.

Invalid policy returns:

`POLICY_VALIDATION_FAILED`

## 15. Activation Conflict

For an exclusive scope, activation must atomically:

1. lock the scope;
2. verify no incompatible ACTIVE version remains;
3. mark prior ACTIVE version SUPERSEDED;
4. activate the new version;
5. emit audit/outbox event;
6. invalidate affected caches.

No ambiguous double-active state is allowed.

## 16. Policy Cache

Caching is allowed only for performance.

Rules:

- cache keys include immutable version ID or scope generation;
- activation invalidates affected scope;
- commands persist resolved version IDs before execution;
- cache failure never falls back to stale policy.

If safe resolution is unavailable:

`POLICY_RESOLUTION_UNAVAILABLE`

and the command fails closed.

## 17. Integrity Hash

APPROVED/ACTIVE policy payloads should store a canonical payload hash.

Purpose:

- detect accidental mutation;
- support audit;
- verify runtime configuration integrity.

## 18. Policy Change Audit

Each lifecycle/change event records:

- policy/version;
- previous/new state;
- actor;
- reviewer/approver;
- reason;
- payload hash;
- scope;
- timestamp;
- correlation ID.

High-impact changes should expose a semantic diff before approval.

## 19. Impact Classification

Policy changes should be classified:

- LOW — metadata/no financial impact;
- MEDIUM — operational behavior;
- HIGH — changes to Advance Rate, limits, reserve thresholds, claim rules, guarantee exposure, ownership/entitlement, authorization, or accounting mappings.

HIGH changes require stronger approval/maker-checker rules.

## 20. Emergency Restrictions

Badban may support explicit time-bounded emergency restrictions such as:

- stop new guarantees;
- suspend provider;
- suspend Asset Type for new transactions;
- increase review requirements.

Emergency restrictions must be scoped, reason-coded, auditable, and must not silently:

- increase guarantee capacity;
- weaken a hard reserve/legal limit;
- change ownership rights;
- erase reconciliation blocks;
- rewrite existing guarantee terms.

## 21. Explicit Migration

If an active obligation is legally permitted to adopt a newer policy:

- create an explicit amendment/migration command;
- validate contractual/legal permission;
- capture old/new snapshots;
- audit actor/reason;
- apply ledger/control effects if required.

Bulk updating historical policy references is forbidden.

## 22. Historical Replay

The platform must answer:

> Why was this amount/state approved at that time?

Replay uses captured:

- inputs;
- valuation;
- policy versions;
- algorithm version;
- risk snapshot;
- rounding.

Fresh external lookups are not used to reconstruct a historical decision.

## 23. Persistence Additions

### policy_versions

- id;
- policy_type;
- policy_code;
- version_number;
- lifecycle_status;
- scope_definition;
- payload;
- payload_hash;
- schema_version;
- effective_from;
- effective_to;
- approved_at;
- activated_at;
- superseded_at;
- created_by;
- approved_by.

### decision_snapshots

- id;
- business_entity_type;
- business_entity_id;
- decision_type;
- policy_pack_id;
- algorithm_code;
- algorithm_version;
- input_payload;
- output_payload;
- input_hash;
- output_hash;
- effective_at;
- created_at.

Decision snapshots are append-only.

## 24. Runtime Components

### PolicyResolver

Responsibilities:

- resolve active pack for context;
- resolve component versions;
- validate scope;
- detect ambiguity/gaps;
- return immutable manifest.

It does not perform domain calculations.

### Deterministic Calculators

Examples:

- ValuationEligibilityCalculator;
- GuaranteeCapacityCalculator;
- PortfolioRiskEvaluator;
- GuaranteeExposureReductionCalculator;
- ClaimEligibilityCalculator;
- ReturnAllocationCalculator.

Each exposes an explicit algorithm version.

## 25. Stable Policy Errors

- `POLICY_PACK_NOT_ACTIVE`;
- `POLICY_SCOPE_AMBIGUOUS`;
- `POLICY_SCOPE_NOT_FOUND`;
- `POLICY_COMPONENT_MISSING`;
- `POLICY_COMPONENT_INCOMPATIBLE`;
- `POLICY_RESOLUTION_UNAVAILABLE`;
- `POLICY_ACTIVATION_CONFLICT`;
- `POLICY_VALIDATION_FAILED`;
- `POLICY_MIGRATION_NOT_ALLOWED`.

## 26. Hard Invariants

1. No real pilot transaction without an ACTIVE Pilot Policy Pack.
2. No material decision uses implicit latest policy.
3. Every material decision stores exact version references.
4. ACTIVE content is immutable.
5. Activation is explicit and audited.
6. Historical transactions never silently adopt new policy.
7. Missing/ambiguous policy fails closed.
8. Algorithm version is separate from policy version.
9. Historical replay uses captured inputs.
10. Policy migration is always explicit.

## 27. Next Technical Contracts

Next:

1. API command/query contracts;
2. domain and integration event contracts;
3. provider adapter contracts;
4. reconciliation engine contract;
5. identity/RBAC and maker-checker contract.
