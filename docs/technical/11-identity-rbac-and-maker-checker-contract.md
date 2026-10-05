# Badban Identity, RBAC, and Maker-Checker Contract

- **Status:** Proposed
- **Date:** 2026-10-05
- **Stage:** Technical
- **Scope:** bounded external-lender pilot
- **Depends on:** Technical Foundation; System Context; API Contracts; Reconciliation Contract; Decision 0014

## 1. Objective

Define authentication, authorization, scope control, privileged-action approval, and separation-of-duties requirements for Badban.

Core rule:

```
Authentication proves who/what you are.
Authorization proves what you may do.
Business policy proves whether the action is currently allowed.
Maker-checker proves the same actor did not both propose and approve a high-impact action.
```

No one of these layers replaces the others.

## 2. Identity Classes

Badban recognizes distinct identity classes:

1. participant identity;
2. internal human staff identity;
3. governance/admin approver identity;
4. auditor/read-only identity;
5. provider/service integration identity;
6. internal workload/service identity.

Each identity class has separate authentication and authorization expectations.

## 3. Human Authentication

Privileged human access should use a centralized identity provider supporting:

- OIDC/OAuth2;
- MFA for privileged users;
- short-lived access tokens;
- session revocation;
- role/claim issuance;
- device/session metadata where available;
- audit of login and privileged session changes.

Password handling should remain in the identity provider, not Badban Core.

## 4. Participant Authentication

Participant authentication must support secure participant-facing access without granting staff/admin capabilities.

Participant authorization is self-scoped by default.

A participant may access only explicitly participant-visible data linked to their own participation context.

Participant identity cannot be used to:

- create authoritative valuations;
- activate providers;
- issue guarantees;
- approve claims;
- resolve reconciliation;
- reverse journals;
- approve policy;
- release collateral through privileged paths.

## 5. Staff Roles

Initial logical roles:

### OPERATIONS

Can:

- perform approved operational commands;
- manage participant/asset workflows within assigned scope;
- view operational workspaces;
- initiate permitted manual provider confirmations.

Cannot:

- approve own high-impact actions;
- modify posted journals;
- bypass risk/legal/reconciliation gates.

### RISK

Can:

- view and evaluate risk;
- work with risk-policy drafts;
- review risk exceptions;
- participate in policy review/approval where governance allows.

Cannot directly alter financial balances or provider facts.

### FINANCE_RECONCILIATION

Can:

- inspect ledger/sub-ledger;
- run reconciliation;
- propose reconciliation resolutions;
- initiate approved financial reversals/adjustments.

Cannot silently edit posted financial history.

### LEGAL_COMPLIANCE

Can:

- manage legal entity/authorization evidence;
- review provider/regulatory scope;
- suspend/flag invalid authorization;
- approve designated compliance checkpoints.

Cannot create financial exposure by itself.

### GOVERNANCE_APPROVER

Can approve designated:

- policy packs;
- high-impact exceptions;
- provider activation;
- maker-checker actions.

Scope remains explicit.

### AUDITOR

Read-only access to authorized:

- audit trail;
- journal;
- policy snapshots;
- reconciliation evidence;
- provider/legal-role evidence.

Cannot execute state-changing business commands.

### SYSTEM_OPERATOR

Technical operational role for runtime support.

Must not receive unrestricted financial mutation authority merely because it administers infrastructure.

## 6. Service Identities

Internal services use workload/service identities distinct from human users.

Each service identity has:

- service name;
- environment;
- allowed API/event scope;
- credential/secret reference;
- expiry/rotation policy;
- audit identity.

A service identity must not impersonate a human actor.

## 7. Provider Identities

Each external provider integration has a distinct identity scoped to that provider.

A lender integration identity can submit only lender-authoritative facts for its provider.

It cannot:

- submit events on behalf of another provider;
- activate policy;
- change legal authorization;
- approve Badban claims directly unless the domain contract explicitly treats the provider action as a claim submission, not approval.

## 8. Authorization Model

Badban authorization combines:

```
Role
AND
Program Scope
AND
Legal Entity Scope
AND
Provider Scope
AND
Resource Scope
AND
Command Permission
AND
Business Preconditions
```

A role grant without the correct resource scope is insufficient.

## 9. Scope Dimensions

Authorization may be constrained by:

- program;
- participant cohort;
- legal entity;
- provider;
- Asset Type;
- product;
- geography/jurisdiction where relevant;
- environment;
- command category.

Scope checks occur server-side.

## 10. Role Assignment

Role assignments are explicit records with:

- identity ID;
- role;
- scope;
- granted by;
- granted at;
- valid from;
- valid until optional;
- status;
- reason/ticket reference where required.

No role may be inferred from email domain, UI route, or job title text.

## 11. Privilege Lifecycle

Privilege lifecycle:

```
REQUESTED
→ APPROVED
→ ACTIVE
→ SUSPENDED / EXPIRED / REVOKED
```

High-privilege role grants may themselves require maker-checker.

Expired/revoked roles fail closed immediately for new actions.

## 12. Deny by Default

Authorization is deny-by-default.

If no explicit permission + scope match exists, access is denied.

There is no implicit admin fallback based on missing policy.

## 13. Command Permission Matrix

Every state-changing command maps to one or more allowed roles.

Examples:

### Operations

May initiate:

- create Asset Position;
- submit guarantee request;
- request reservation;
- initiate participant exit;
- record manual provider evidence where authorized.

### Risk

May:

- trigger risk evaluation;
- review risk-policy drafts;
- approve designated risk controls depending on governance configuration.

### Finance/Reconciliation

May:

- run reconciliation;
- propose resolution;
- initiate journal reversal;
- record recovery receipt where operationally assigned.

### Legal/Compliance

May:

- verify/suspend authorization;
- approve legal/compliance review checkpoints.

### Governance Approver

May:

- approve/activate policy;
- activate/suspend provider;
- approve high-impact reconciliation resolution;
- approve exceptional financial corrections.

The exact matrix is configuration/version controlled, not hard-coded by UI alone.

## 14. Read Permission Model

Read permissions are separate from write permissions.

Examples:

- participant: own summary only;
- operations: assigned cohort/program;
- risk: risk-required financial aggregates;
- finance: financial/reconciliation scope;
- auditor: broad read-only evidence within authorized entity scope.

Possession of read access does not imply permission to execute commands.

## 15. Maker-Checker Principle

A high-impact action may require two distinct authorized human identities:

```
Maker proposes/submits.
Checker independently approves.
```

The same identity must not satisfy both roles.

## 16. Maker-Checker Required Actions

At minimum, configuration should support mandatory maker-checker for:

- Policy Pack approval/activation;
- provider activation;
- high-impact legal authorization verification;
- material/critical reconciliation resolution;
- claim approval above configured threshold or all claim approvals if governance requires;
- claim settlement;
- collateral enforcement;
- exceptional collateral release;
- journal reversal;
- manual legal guarantee issuance confirmation;
- emergency risk override;
- exceptional participant exit finalization;
- high-privilege role grant/revocation.

Thresholds/scope come from versioned policy.

## 17. Approval Request Aggregate

Introduce **ApprovalRequest**.

Fields:

- id;
- action_type;
- target_type;
- target_id;
- maker_identity_id;
- checker_identity_id nullable;
- required_checker_role;
- scope;
- payload_hash;
- reason;
- evidence_refs;
- status;
- expires_at nullable;
- created_at;
- approved_at nullable;
- rejected_at nullable;
- cancelled_at nullable;
- version.

States:

```
PENDING
→ APPROVED
| REJECTED
| CANCELLED
| EXPIRED
```

## 18. Approval Payload Integrity

Maker-checker approval must bind to the exact proposed action.

Store a canonical payload hash.

If the underlying action payload changes after approval request creation:

`APPROVAL_PAYLOAD_CHANGED`

The approval becomes invalid and a new approval is required.

## 19. Self-Approval Prevention

Hard invariant:

```
maker_identity_id != checker_identity_id
```

for actions requiring separation of duties.

This must be enforced server-side and preferably protected by a database constraint where practical.

Shared accounts are prohibited for privileged operations.

## 20. Checker Scope Validation

Checker must independently satisfy:

- required role;
- target program/legal entity/provider scope;
- active privilege;
- maker-checker separation;
- any policy-specific qualification.

A globally privileged role must not automatically bypass entity/program scope unless explicitly designed and audited.

## 21. Approval Expiry

High-impact approvals may expire.

If approval is older than policy-valid window or target state/version changed materially:

- approval cannot be executed;
- new approval is required.

No stale approval may authorize a changed transaction.

## 22. Target Version Binding

Approval request should capture expected target aggregate version.

If aggregate version changed before execution:

`APPROVAL_TARGET_VERSION_CONFLICT`

The action is re-evaluated.

This prevents approval of one state being reused after the resource changes.

## 23. Two-Step Execution

High-impact flow:

```
Maker command
→ create ApprovalRequest(PENDING)
→ checker approves
→ execution service revalidates:
   identity
   scope
   aggregate version
   policy
   legal/risk/reconciliation gates
→ domain command executes
```

Checker approval alone does not bypass business preconditions.

## 24. Rejection

Checker may reject with:

- reason code;
- comment;
- evidence if required.

Rejected approval requests remain immutable/auditable.

Maker must create a new request for a revised action.

## 25. Emergency Access

Badban may support tightly controlled emergency access, but no hidden "superuser" financial override.

Emergency access requires:

- explicit break-glass role;
- strong authentication/MFA;
- reason;
- bounded duration;
- elevated logging;
- post-event review;
- no silent audit suppression.

Break-glass does not automatically bypass hard legal/business invariants.

## 26. Separation of Duties

System should prevent incompatible role combinations where governance requires.

Potential conflicts:

- maker + checker for same action scope;
- finance poster + independent financial reviewer;
- provider onboarding maker + provider activation checker;
- policy author + sole policy approver;
- reconciliation proposer + resolver/approver for critical case.

Exact SoD matrix is policy-controlled.

## 27. Delegation

Delegation must be explicit.

A delegate record includes:

- delegator;
- delegate;
- role/action scope;
- start/end time;
- reason;
- approval;
- audit.

Delegation must not weaken maker-checker or role conflict rules.

## 28. Impersonation

Administrative impersonation of participants should be avoided.

If support-view capability is necessary, use explicit:

- read-only support mode;
- banner/indicator;
- scoped duration;
- audit;
- no hidden mutation authority.

## 29. Session Security

Privileged sessions should support:

- short inactivity timeout;
- absolute session lifetime;
- re-authentication for sensitive actions where required;
- immediate revocation on role suspension;
- MFA step-up for high-impact commands if supported.

## 30. Token Claims

Tokens may include:

- subject;
- identity type;
- role references;
- coarse scope claims.

Fine-grained authorization must still be checked against server-side current grants.

Do not place full dynamic authorization truth solely in long-lived tokens.

## 31. Authorization Cache

Authorization grants may be cached briefly if revocation semantics remain safe.

Rules:

- cache is keyed by identity/scope/version;
- role revocation invalidates cache;
- privileged commands may require fresh authorization read;
- cache failure must not grant access.

## 32. Audit Requirements

Every privileged authorization decision should record enough context to answer:

- who acted;
- what command;
- target resource;
- role used;
- scope used;
- approval request if any;
- checker identity;
- result;
- denial reason where relevant;
- timestamp;
- correlation ID.

## 33. Access Review

Badban should support periodic access review for privileged roles.

Review output identifies:

- active high-privilege users;
- stale grants;
- expired delegations;
- unused privileged roles;
- role conflicts;
- provider/service credentials nearing expiry.

Cadence is governance policy.

## 34. Joiner / Mover / Leaver

Identity lifecycle must support:

### Joiner

Minimum required role only.

### Mover

Old scope/roles removed before or with new assignment.

### Leaver

Privileged sessions revoked and roles deactivated promptly.

Historical audit remains intact.

## 35. Provider/Service Credential Authorization

Service/provider identities are authorized by capability and resource scope, not human roles.

Examples:

- lender adapter may write only lender inbound event endpoints;
- reconciliation worker may run reconciliation but cannot activate Policy Pack;
- outbox publisher may publish events but cannot mutate domain aggregates directly.

## 36. API Error Codes

Stable authorization/approval errors include:

- `AUTHENTICATION_REQUIRED`;
- `AUTHORIZATION_DENIED`;
- `RESOURCE_SCOPE_DENIED`;
- `ROLE_INACTIVE`;
- `ROLE_EXPIRED`;
- `MAKER_CHECKER_REQUIRED`;
- `SELF_APPROVAL_FORBIDDEN`;
- `APPROVAL_NOT_FOUND`;
- `APPROVAL_EXPIRED`;
- `APPROVAL_REJECTED`;
- `APPROVAL_PAYLOAD_CHANGED`;
- `APPROVAL_TARGET_VERSION_CONFLICT`;
- `CHECKER_SCOPE_INVALID`;
- `SEGREGATION_OF_DUTIES_VIOLATION`.

## 37. Persistence Additions

### identities

- id;
- identity_type;
- external_subject;
- status;
- created_at;
- updated_at.

### role_grants

- id;
- identity_id;
- role_code;
- scope_type;
- scope_id;
- valid_from;
- valid_until;
- status;
- granted_by;
- reason_ref;
- version.

### approval_requests

As defined above.

### delegations

- id;
- delegator_identity_id;
- delegate_identity_id;
- role/action scope;
- valid_from;
- valid_until;
- status;
- approval_request_id nullable;
- created_at.

### access_review_findings

Append-only review evidence/status.

## 38. API Additions

Logical endpoints:

```
GET  /api/v1/admin/roles
GET  /api/v1/admin/role-grants
POST /api/v1/admin/role-grants
POST /api/v1/admin/role-grants/{id}/revoke

GET  /api/v1/approvals
GET  /api/v1/approvals/{id}
POST /api/v1/approvals/{id}/approve
POST /api/v1/approvals/{id}/reject
POST /api/v1/approvals/{id}/cancel
```

No endpoint may approve and execute a protected high-impact action under the same actor identity in one step when maker-checker is required.

## 39. Test Contract

Tests must cover:

- participant self-scope;
- staff cross-program denial;
- provider cross-provider denial;
- expired role;
- revoked role/session;
- self-approval rejection;
- checker wrong scope;
- maker/checker success;
- target version changed after approval;
- payload changed after approval;
- approval expiry;
- SoD conflict;
- delegated authority expiry;
- service identity least privilege;
- auditor read-only guarantee.

High-impact command tests must prove that unauthorized or unapproved calls produce no domain/ledger side effect.

## 40. Hard Invariants

1. Authorization is deny-by-default.
2. Role alone is insufficient without matching scope.
3. Participant access is self-scoped unless explicitly authorized otherwise.
4. Provider identities are provider-scoped.
5. High-impact maker/checker actions require distinct identities.
6. Approval binds to exact payload and target version.
7. Checker approval never bypasses domain/legal/risk/reconciliation gates.
8. Shared privileged accounts are forbidden.
9. Break-glass is explicit, time-bounded, and audited.
10. No role or service identity gets arbitrary direct ledger/state mutation authority.

## 41. Next Technical Contracts

Next:

1. Security and Secrets Contract;
2. Observability and Operational Readiness Contract;
3. Deployment / Runtime Topology and Non-Functional Requirements;
4. Technical Stage Completion Review.
