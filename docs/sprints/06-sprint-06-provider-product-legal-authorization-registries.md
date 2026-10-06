# Sprint 06 — Provider/Product and Legal Authorization Registries

- **Status:** Accepted
- **Date:** 2026-10-06
- **Stage:** Sprint Planning
- **Scope:** bounded external-lender pilot
- **Entry Gate:** Decision 0023; Sprint 05 Code + Code Review Complete
- **Depends on:** BL-007, BL-013 complete through Code Review
- **Code Authorization:** GRANTED BY DECISION 0030

## 1. Sprint Goal

Deliver the authoritative provider/product and legal-authorization registries required before any guarantee request or reservation path may rely on a regulated counterparty.

Sprint 06 contains only:

- **BL-017 — Credit Provider and Product Version Registry**
- **BL-018 — Legal Entity Role and Authorization Registry**

No guarantee request, reservation, issuance, lender event, or financial side effect is authorized.

## 2. Why BL-016 Is Not Selected

BL-016 — Guarantee Capacity Read Model is not Code-authorized in this Sprint.

Although its backlog dependency points to BL-015, Technical 07 §14 requires the read model to return and explain:

- reserved capacity;
- active exposure;
- other approved holds;
- portfolio controls;
- valuation freshness;
- policy/version evidence.

Authoritative reservation/exposure/hold and portfolio-control sources do not yet exist in the implemented system. Sprint 06 must not synthesize these values as zero or otherwise invent them.

BL-016 remains pending until its authoritative source contracts are available.

## 3. BL-018 First Within the Sprint

The legal authorization registry is implemented before provider activation semantics depend on it.

Accepted authorization lifecycle:

```
PENDING_VERIFICATION
  ↓ verified
VALID
  ├─ temporary restriction → SUSPENDED
  ├─ date reached → EXPIRED
  ├─ revoked → REVOKED
  └─ superseded → SUPERSEDED
```

New regulated action requires a VALID authorization and scope match.

## 4. Legal Entity and Authorization Contract

The registry must represent explicit legal entities and authorization evidence without assuming that Badban Core is itself licensed for a regulated function.

At minimum, accepted data may include:

- legal entity identity and legal/company identifier;
- regulated role(s);
- regulator/competent authority;
- authorization/license type;
- authorization/license identifier;
- effective date;
- expiry/renewal date where applicable;
- permitted product scope;
- permitted Asset Types;
- evidence/reference;
- last compliance review date;
- lifecycle status.

The system must support roles needed by the accepted architecture, including:

- Guarantee Issuer;
- External Lender;
- Asset Manager / Custodian;
- Banking / Payment Rails;
- collateral/registry or other regulated provider roles where applicable.

No role is inferred merely because an entity is a Badban partner.

## 5. Legal Authorization Controls

Sprint 06 must enforce:

- missing authorization fails closed;
- expired authorization fails closed for new regulated actions;
- suspended/revoked authorization fails closed;
- scope mismatch fails closed;
- authorization evidence is retained;
- authorization validity is time-aware;
- verification/suspension is explicit and audited;
- high-impact authorization verification supports existing maker-checker controls;
- a generic Badban identity is never treated as implicit regulated authority.

## 6. BL-017 Provider Registry

Provider lifecycle uses the accepted state machine:

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

- only ACTIVE provider may create new exposure in future authorized flows;
- SUSPENDED/EXPIRED/TERMINATED never erase historical obligations;
- provider activation is explicit and audited;
- provider activation is a high-impact action and must use existing maker-checker support;
- provider activation must not bypass required legal authorization;
- technical readiness alone never activates a provider.

## 7. Credit Product Version Registry

Provider identity and product version are distinct.

Every product version must preserve explicit provider/lender-of-record linkage and versioned terms.

The registry may represent accepted product-rule categories from Decision 0011, including:

- amount constraints;
- currency;
- tenor model;
- repayment structure;
- pricing/fees;
- grace rules;
- eligibility conditions;
- guarantee-exposure mode;
- early repayment rules;
- delinquency/claim rules;
- effective dates;
- lifecycle status.

Sprint 06 does **not** choose or hard-code production values for any of these fields.

Missing product terms must never be guessed.

Material product changes must produce a new version rather than silently rewriting terms already captured by an obligation.

## 8. Direct Lending Boundary

For the bounded pilot:

```
Badban Direct Lending = DISABLED
```

Sprint 06 must not create an active direct-lending provider/product path.

The architecture may remain capable of representing future channels, but no direct-lending activation, liquidity model, receivable, servicing, accounting, or regulated lending behavior is authorized.

## 9. Accepted API Surface

Sprint 06 may implement the already accepted Technical 07 §26 provider/legal-authorization endpoints:

```
GET  /api/v1/admin/providers
POST /api/v1/admin/providers
GET  /api/v1/admin/providers/{id}
POST /api/v1/admin/providers/{id}/activate
POST /api/v1/admin/providers/{id}/suspend

GET  /api/v1/admin/legal-entities/{id}/authorizations
POST /api/v1/admin/legal-entities/{id}/authorizations
POST /api/v1/admin/authorizations/{id}/verify
POST /api/v1/admin/authorizations/{id}/suspend
```

Product-version persistence/application services and authorized read paths may be implemented as required by BL-017.

No new public product endpoint is invented unless an accepted API contract already exists or a separate decision explicitly authorizes it.

## 10. Authorization and Maker-Checker

Use existing RBAC and ApprovalRequest infrastructure.

At minimum:

- LEGAL_COMPLIANCE is the legal/compliance operating role;
- GOVERNANCE_APPROVER may activate/suspend providers where the accepted authorization matrix allows;
- auditor access is read-only;
- self-approval is forbidden;
- approval binds to exact payload and target version;
- checker scope must match the target legal entity/provider scope when applicable.

No UI or route name substitutes for server-side authorization.

## 11. Immutability and History

The registries must preserve historical explainability.

At minimum:

- activation/suspension/verification changes are audited;
- product versions referenced by future obligations remain readable;
- legal authorization history remains readable after expiry/revocation/supersession;
- provider history remains readable after suspension/expiry/termination;
- active/historical references are not silently redirected to a newer product or authorization.

## 12. Acceptance Tests

Tests must prove at least:

- provider and product version are distinct;
- provider activation is impossible without required approval;
- provider activation cannot bypass legal authorization;
- SUSPENDED/EXPIRED/TERMINATED provider cannot authorize new exposure;
- Direct Lending is not activatable in the bounded pilot path;
- product terms are explicit and versioned;
- no production product values are invented;
- legal authorization scope and validity are enforced;
- missing/expired/suspended/revoked authorization fails closed;
- legal authorization verify/suspend is audited;
- maker-checker self-approval fails;
- approval payload/version binding is enforced;
- auditor remains read-only;
- history remains queryable;
- no guarantee/reservation/ledger/provider-network side effect occurs.

## 13. Definition of Done

Sprint 06 Code is Done through Code Review only when:

- BL-017 is implemented within the accepted provider/product registry contract;
- BL-018 is implemented within the accepted legal authorization contract;
- accepted API endpoints are covered;
- full format/lint/type/migration/test/security/dependency/container CI gates are green;
- maker-checker and RBAC controls are proven;
- no Direct Lending path is activated;
- no production provider/product/legal values are introduced;
- no BL-019/020/021/032 or downstream workflow is introduced;
- Code Review completes.

Stage remains Deferred under Decision 0023.

## 14. Explicit Non-Goals

Sprint 06 does not implement:

- BL-016 Guarantee Capacity Read Model;
- BL-019 Guarantee Request Aggregate;
- BL-020 Atomic Backing Reservation;
- BL-021 Reservation Expiry;
- BL-032 Portfolio Risk Snapshot/Gate;
- Guarantee Issuer adapter;
- lender adapter;
- legal guarantee issuance;
- external loan mirror;
- ledger posting;
- claims/recovery;
- return allocation;
- participant exit financial reconciliation;
- Direct Lending;
- real provider credentials;
- real legal licenses/authorizations;
- production product values;
- Stage;
- QA/Testing gate completion;
- Release Approval;
- Production;
- real-money use.

## 15. Approval Effect

This Sprint 06 plan is Accepted.

Decision 0030 grants Code authorization only for BL-017 and BL-018 under the boundaries above.
