# Sprint 02 — Identity and Core Participant / Asset State

- **Status:** Completed
- **Date:** 2026-10-05
- **Stage:** Code + Code Review Complete
- **Scope:** bounded external-lender pilot
- **Entry Gate:** Decision 0019; Decision 0023
- **Depends on:** Sprint 01 foundation merged and reviewed
- **Code Authorization:** GRANTED BY DECISION 0024
- **Code Review:** COMPLETE BY DECISION 0025

## 1. Sprint Goal

Deliver Slice 1 of the accepted Product Backlog so an authenticated and explicitly scoped Badban operator can create and inspect the first authoritative participant/program/asset state while preserving ownership classification, deny-by-default authorization, auditability, and the accepted security boundaries.

Sprint 02 does not create guarantee capacity, legal guarantee issuance, external lending, ledger postings, or real-money behavior.

## 2. Selected Backlog Items

Sprint 02 delivered:

- **BL-006 — Central Identity Integration**
- **BL-007 — RBAC and Scoped Authorization Engine**
- **BL-009 — Program and Participation Episode**
- **BL-010 — Asset Type Registry**
- **BL-011 — Asset Position and Ownership/Funding Classification**
- **BL-044 — Audit and Evidence Trace baseline**

This is the accepted Product Backlog **Slice 1 — Identity and Core Participant/Asset State**.

## 3. Dependency Order Inside Sprint

```
Sprint 01 Foundation
→ BL-006 Central Identity
→ BL-007 Scoped Authorization
→ BL-009 Program / Participation Episode
→ BL-010 Asset Type Registry
→ BL-011 Asset Position
→ BL-044 Audit / Evidence Trace
```

BL-044 infrastructure can be developed in parallel once authenticated actor identity is available, but material audit records must bind to the server-authenticated actor rather than client-supplied identity fields.

## 4. Implementation Choices

### Identity Provider Boundary

Use the Accepted Decision 0020 Keycloak/OIDC choice through a provider-neutral OIDC validation seam.

Sprint 02 should implement:

- OIDC issuer/discovery configuration;
- JWT signature validation through issuer JWKS;
- issuer, audience, expiry/not-before validation;
- external subject mapping to a Badban identity;
- identity class distinction for human/service/provider contexts where applicable;
- environment-scoped identity configuration;
- no local Badban password store;
- no client-authored actor identity.

Local/CI may use a deterministic test issuer/Keycloak-compatible setup.

No production identity realm or production credentials are implied.

### Authorization Source of Truth

Badban remains authoritative for current fine-grained grants.

Implement persisted role grants with:

- identity;
- role code;
- scope type/id;
- validity window;
- status;
- grant/revocation metadata;
- version.

Authorization is deny-by-default and requires both permission and matching scope.

Token roles/claims may assist authentication/context, but do not replace current server-side role-grant checks.

### Initial Roles

Use the Accepted Technical role codes where needed:

- OPERATIONS
- RISK
- FINANCE_RECONCILIATION
- LEGAL_COMPLIANCE
- GOVERNANCE_APPROVER
- AUDITOR
- SYSTEM_OPERATOR

Sprint 02 needs only the permissions required for its selected commands and reads.

No universal admin bypass is introduced.

### Program / Participation Episode

Implement authoritative Program and ParticipationEpisode state with explicit aggregate versions and actor/audit fields.

Participation Episode must remain distinct from later financial closure.

Sprint 02 may support only the minimum lifecycle required for Slice 1 creation/read behavior; it must not invent unresolved exit or entitlement rules beyond the Accepted contracts.

### Asset Type Registry

Asset Type must remain configurable and must not encode gold as the domain model.

Represent at minimum:

- stable Asset Type identity;
- version/configuration identity where needed;
- unit;
- precision/scale;
- valuation source reference metadata;
- eligibility metadata;
- custody/restriction metadata;
- lifecycle/active state required to block unapproved/inactive use.

The production Asset Type remains a later activation decision.

### Asset Position

Asset Position must bind to:

- Participation Episode / Program;
- Asset Type;
- quantity using exact numeric arithmetic;
- ownership/funding classification;
- custody/ownership references where applicable;
- aggregate version and audit fields.

Allowed ownership/funding classifications for this Sprint are exactly:

- `PARTICIPANT_OWNED`
- `PROGRAM_ATTRIBUTED`

Market valuation and guarantee capacity must not be persisted as mutable Asset Position balances.

### Audit and Evidence Trace

Introduce append-only audit records for material Sprint 02 commands.

Capture at minimum:

- authenticated actor/system identity;
- command/action;
- target type/id;
- correlation ID;
- outcome;
- relevant scope;
- evidence references when present;
- timestamp.

Evidence references are opaque references/metadata only.

Generic audit/log payloads must not copy secrets, raw restricted documents, access tokens, or unnecessary PII.

## 5. Proposed API Surface

The exact OpenAPI implementation may refine naming while preserving the Accepted API command/query style.

Logical Sprint 02 endpoints include:

```
GET  /api/v1/me
GET  /api/v1/me/grants

POST /api/v1/programs
GET  /api/v1/programs/{id}

POST /api/v1/programs/{program_id}/participation-episodes
GET  /api/v1/participation-episodes/{id}

POST /api/v1/asset-types
GET  /api/v1/asset-types
GET  /api/v1/asset-types/{id}

POST /api/v1/asset-positions
GET  /api/v1/asset-positions/{id}
```

Administrative grant-management endpoints may be introduced only to the minimum extent needed to exercise and test current grants safely.

No generic force-state or arbitrary table mutation API is permitted.

## 6. Authorization Expectations

At minimum:

### OPERATIONS

May, when explicitly scoped:

- create/read Participation Episodes in assigned Program scope;
- create/read Asset Positions in assigned Program/participant scope;
- read approved Asset Types.

### AUDITOR

May read authorized Sprint 02 state and audit evidence.

Must not create or mutate Program/Participation/Asset state.

### Participant

If participant authentication is wired in this Sprint, access is self-scoped only.

Participant write behavior is not required unless explicitly covered by a selected backlog item.

### Other Roles

No permission exists merely because a role code exists.

Each command/read must declare its allowed role + scope requirements.

## 7. Persistence Deliverables

Expected migration additions include only Sprint 02 scope:

- identities;
- role_grants;
- programs;
- participation_episodes;
- asset_types and/or versioned asset-type records consistent with the accepted domain model;
- asset_positions;
- append-only audit_events;
- opaque evidence reference metadata where needed.

All mutable aggregate roots use optimistic versioning.

Foreign keys, uniqueness, check constraints, and indexes must enforce obvious integrity rules.

## 8. Definition-of-Ready Evidence

### BL-006

Ready.

BL-001 and BL-003 are complete in Sprint 01; Keycloak/OIDC and secret/config boundaries are already selected.

### BL-007

Ready in the same approved Sprint sequence after BL-006.

Technical 11 defines role/scope/deny-by-default behavior.

### BL-009

Ready in sequence after BL-007.

Persistence foundation BL-004 is Done; Program/Participation contracts are Accepted.

### BL-010

Ready in sequence after BL-009.

Decision 0001 explicitly requires configurable Asset Type; gold must not be hard-coded.

### BL-011

Ready in sequence after BL-009 and BL-010.

Decision 0003 defines the two ownership/funding classifications.

### BL-044

Ready.

BL-004 is Done and BL-006 is included in this Sprint.

## 9. Acceptance Tests

Sprint 02 must prove at least the following.

### Authentication

- valid issuer/audience/signature token authenticates;
- invalid signature is rejected;
- expired/not-yet-valid token is rejected;
- wrong issuer/audience is rejected;
- actor identity comes from validated authentication context, not request payload;
- provider/service identity cannot be treated as a human user merely by changing request fields.

### Authorization

- no grant => deny;
- inactive/expired/revoked grant => deny;
- correct role but wrong Program scope => deny;
- correct role and matching scope => allow;
- read permission does not imply write permission;
- AUDITOR cannot execute write commands;
- cross-scope access produces no state change.

### Program / Participation

- authorized creation succeeds;
- stale aggregate version is rejected where a mutable command applies;
- unauthorized creation/read is rejected;
- Participation Episode remains linked to explicit Program and participant context;
- Program Exit is not modeled as financial closure.

### Asset Type

- configurable non-gold Asset Type can be represented;
- unit/precision metadata is validated;
- inactive/unapproved type cannot be used for a new pilot Asset Position;
- no market value or guarantee capacity is stored as mutable Asset Type/Position truth.

### Asset Position

- exact quantity persists without binary-float loss;
- `PARTICIPANT_OWNED` succeeds;
- `PROGRAM_ATTRIBUTED` succeeds;
- invalid ownership classification fails;
- Program/Participation/Asset Type scope mismatch fails;
- duplicate/idempotent command behavior is safe where command retry applies.

### Audit / Evidence

- successful material command writes audit with authenticated actor + correlation;
- rejected privileged/scoped command records the required security/audit outcome where the contract requires it;
- audit row is append-only through normal runtime paths;
- test secret/token values do not appear in structured logs or generic audit payloads;
- evidence references remain opaque.

## 10. Sprint Definition of Done

Sprint 02 is Done only when:

- its Code authorization is explicitly Accepted;
- migrations apply from Sprint 01 schema and drift check is green;
- OIDC authentication contract tests are green;
- deny-by-default scoped authorization tests are green;
- Program/Participation tests are green;
- Asset Type configurability tests are green;
- Asset Position ownership/funding tests are green;
- audit/evidence tests are green;
- lint/type/security/dependency/container CI gates are green;
- no capacity/guarantee/loan/ledger Business behavior was introduced;
- documentation matches implementation reality;
- Code Review is completed.

## 11. Explicit Non-Goals

Sprint 02 must not implement:

- Maker-Checker / ApprovalRequest;
- valuation observations;
- Policy Pack lifecycle;
- PolicyResolver / DecisionSnapshot;
- guarantee capacity;
- Credit Provider/Product Registry;
- Legal Entity Authorization Registry;
- guarantee request/reservation;
- guarantee issuance;
- lender adapters;
- external loan mirror;
- ledger/posting templates;
- risk/reserve;
- claim/recovery;
- return allocation;
- exit financial reconciliation;
- Stage deployment;
- Production;
- Direct Lending.

## 12. Stage Deferral

Decision 0023 permits iterative Sprint development while Stage is unavailable.

Sprint 02 completion therefore adds to the accumulated Stage candidate; it does not satisfy or bypass the future Stage gate.

## 13. Completion Effect

Sprint 02 was Accepted and implemented under Decision 0024.

Code Review completed under Decision 0025 and PR #2 was merged to `main`.

Stage remains deferred under Decision 0023; Sprint 02 is part of the accumulated future Stage candidate.
