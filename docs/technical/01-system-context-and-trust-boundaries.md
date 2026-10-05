# Badban System Context and Trust Boundaries

- **Status:** Accepted
- **Date:** 2026-10-05
- **Stage:** Technical
- **Scope:** bounded external-lender pilot
- **Depends on:** Technical Foundation; Decisions 0014–0017

## 1. Context

Badban is a financial orchestration platform that coordinates asset-backed guarantee capacity, external lending, regulated legal roles, financial sub-ledgers, and reconciliation.

For the bounded pilot, Badban is **not** the lender of record and must not assume that Badban Core is itself the legal guarantor, custodian, or asset manager.

The system therefore sits between participants/operators and regulated external parties.

## 2. Primary System Context

```
Participant / Operations Users
            │
            ▼
      Badban Web/API
            │
            ▼
      Badban Core
   ┌────────┼─────────┐
   │        │         │
   ▼        ▼         ▼
Custodian  Guarantee  External
/ Asset    Issuer     Lender
Provider
   │        │         │
   └────────┼─────────┘
            ▼
 External Registries /
 Settlement / Evidence
```

## 3. Trust Zones

### Zone A — Untrusted Client Zone

Includes:

- participant browser/mobile client;
- operations browser;
- admin browser;
- auditor browser.

Rules:

- clients never receive provider secrets;
- clients never authoritatively calculate balances, guarantee capacity, reserve status, or policy outcomes;
- all material actions are server-authorized;
- client-supplied financial amounts are treated as requests, not trusted facts.

### Zone B — Badban Application Zone

Includes:

- API/application services;
- domain modules;
- policy engine;
- ledger;
- reconciliation;
- audit;
- outbox/inbox processing.

This is the authoritative execution zone for Badban-owned business state.

Rules:

- privileged domain transitions occur only here;
- ledger writes occur only here;
- policy version resolution occurs only here;
- no direct database mutation from clients or provider callbacks.

### Zone C — Badban Data Zone

Includes:

- primary transactional database;
- append-only journal data;
- outbox/inbox tables;
- immutable audit records;
- evidence metadata.

Rules:

- access restricted to application/runtime identities;
- no public network access;
- backups encrypted;
- database credentials are runtime secrets;
- audit/journal mutation is prohibited outside controlled migrations/repair processes.

### Zone D — External Regulated Provider Zone

Includes:

- lender;
- guarantee issuer;
- custodian/asset provider;
- payment/banking rail;
- collateral registry;
- regulator/authority integrations where applicable.

These systems are outside Badban's trust boundary.

Their responses are authoritative only for the facts assigned to them by Business decisions.

Every inbound fact must be authenticated, deduplicated, persisted with evidence/reference, and reconciled.

### Zone E — Secrets and Signing Zone

Includes:

- API credentials;
- signing keys;
- encryption keys;
- webhook verification secrets;
- mTLS credentials.

Rules:

- secrets are not stored in ordinary application tables;
- secrets are not returned to clients;
- secrets are not written to logs;
- access is least-privilege and environment-scoped;
- rotation must not require rewriting financial history.

## 4. External Actors

### Participant

Can:

- view own eligible program/asset/loan/guarantee/entitlement information;
- submit permitted requests;
- provide required consent/evidence.

Cannot:

- directly create valuation;
- set guarantee capacity;
- issue guarantee;
- mark repayment;
- release collateral;
- alter ledger state.

### Operations User

Can perform controlled operational workflows.

Cannot bypass:

- risk gate;
- legal-role gate;
- reconciliation gate;
- maker/checker requirement where configured.

### Risk User

Can:

- review risk states;
- manage approved policy drafts/inputs subject to governance;
- review exceptions.

Cannot directly mutate active guarantee exposure or financial balances.

### Finance/Reconciliation User

Can:

- reconcile external records;
- investigate mismatches;
- initiate approved financial corrections.

Corrections must use reversal/adjustment workflows.

### Legal/Compliance User

Can manage:

- legal entity metadata;
- authorization evidence;
- compliance review status;
- legal-role eligibility.

Cannot unilaterally create financial exposure.

### Governance/Admin Approver

Can approve versioned policy artifacts and designated high-impact actions.

Approval authority must be explicit and auditable.

### Auditor

Read-only access to:

- journal;
- audit events;
- policy snapshots;
- reconciliation evidence;
- provider/legal-role evidence.

## 5. External Systems

### External Lender

Authoritative for:

- lender credit decision;
- external loan identifier;
- disbursement;
- repayment receipts;
- lender-side outstanding principal;
- lender delinquency servicing.

Badban mirrors these facts.

### Guarantee Issuer

Authoritative for:

- legally issued guarantee instrument;
- external guarantee identifier;
- legal issuance/cancellation/settlement evidence.

Badban remains authoritative for internal guarantee workflow and capacity reservation.

### Custodian / Asset Provider

Authoritative for externally held asset/custody evidence assigned to it.

Badban remains authoritative for its internal Asset Position model and ownership/funding classification, subject to reconciliation.

### Collateral Registry

Authoritative for legally registered pledge/encumbrance/release when external registration is required.

Badban's internal encumbrance model must reconcile to it.

### Bank / Settlement Rail

Authoritative for real cash movement evidenced by settlement references.

A Badban journal posting alone does not prove external cash movement.

## 6. Authentication Boundaries

### Human Users

Technical implementation should use a centralized identity provider supporting:

- OIDC/OAuth2;
- MFA for privileged roles;
- short-lived access tokens;
- role/claim mapping;
- session revocation;
- audit of privileged authentication.

### Provider Integrations

Use one or more of:

- mTLS;
- signed requests;
- OAuth2 client credentials;
- provider-specific cryptographic signatures;
- IP/network restrictions where appropriate.

Provider authentication must be isolated per provider.

### Webhooks / Callbacks

Every inbound callback must be:

1. authenticated;
2. timestamp/nonce checked where available;
3. deduplicated;
4. persisted as raw/evidence metadata where permitted;
5. processed asynchronously after acceptance.

## 7. Authorization Model

Authorization is both **role-based** and **context-based**.

A command is permitted only when:

```
Identity Role
AND
Legal Entity / Program Scope
AND
Resource Scope
AND
Business Preconditions
AND
Policy Authorization
```

Examples:

- a finance user in Program A cannot alter Program B balances;
- an operations user cannot approve their own maker/checker action;
- a provider integration identity can only submit facts for its own provider;
- a suspended provider cannot create new regulated exposure.

## 8. Data Classification

### Restricted

- national/legal identifiers;
- participant financial data;
- provider credentials;
- legal documents;
- claim evidence;
- bank/account references;
- signing keys.

### Confidential

- risk policies;
- provider contracts metadata;
- reconciliation exceptions;
- operational audit details.

### Internal

- non-sensitive operational configuration;
- service health and internal metrics without personal data.

### Participant-visible

Only explicitly designed statement/read-model fields.

Internal risk, audit, provider credentials, and unrelated participant information must not leak through participant APIs.

## 9. Data Minimization

Each integration should exchange only data required for the specific role.

Examples:

- lender does not need unrelated participant asset history beyond agreed guarantee/collateral information;
- custodian does not need lender pricing data unless required;
- participant UI does not need internal reserve methodology details unless product disclosure requires it.

## 10. Evidence Boundary

External facts used for financial/legal transitions must preserve evidence metadata:

- provider;
- source reference;
- external identifier;
- signed/hash reference where applicable;
- event timestamp;
- received timestamp;
- verification result;
- reconciliation status.

Evidence content may be stored outside the transactional database, but the immutable reference must remain in Badban.

## 11. High-Risk Commands

The following commands require elevated authorization and may require maker/checker:

- activate/suspend provider;
- approve policy pack;
- manually confirm legal guarantee issuance;
- manually resolve material reconciliation mismatch;
- approve claim;
- settle claim;
- enforce collateral;
- release collateral in exceptional cases;
- reverse posted financial event;
- finalize participant exit with open exception;
- emergency risk override.

No emergency override may silently bypass audit.

## 12. Fail-Closed Boundaries

The system must fail closed when:

- legal authorization is expired/suspended;
- provider authentication cannot be verified;
- valuation is stale beyond policy;
- required reconciliation is materially stale/mismatched;
- one-to-one loan/guarantee amount fails;
- ledger posting fails;
- policy version is missing;
- maker/checker approval is required but absent.

## 13. Logging Rules

Logs must not contain:

- access tokens;
- provider secrets;
- private keys;
- full sensitive documents;
- unnecessary national identifiers;
- raw bank credentials.

Structured logs should contain:

- correlation ID;
- business entity ID;
- event type;
- actor/system identity;
- result;
- reason code;
- latency;
- provider name/ID where relevant.

## 14. Network Boundary

Proposed deployment zones:

```
Public Edge
  ↓
API Gateway / WAF
  ↓
Private Application Network
  ↓
Private Data Network
```

Provider outbound integrations originate from controlled egress.

Inbound provider callbacks terminate at a controlled public integration endpoint and never connect directly to the database.

## 15. Business Continuity

Loss of an external provider must not corrupt internal state.

If provider access is unavailable:

- commands remain pending/retryable where appropriate;
- state remains explicit;
- no inferred success;
- reconciliation marks stale;
- business gates block unsafe follow-up actions.

## 16. Pilot-Scope Trust Constraints

For the initial pilot:

- one active lender integration;
- one active Guarantee Issuer;
- one production Asset Type;
- direct lending disabled;
- no multi-currency;
- no autonomous AI financial decisions.

These constraints reduce the number of simultaneous trust relationships and simplify reconciliation.

## 17. Technical Consequences

This context implies the Technical design must include:

- centralized identity;
- explicit authorization service/policy checks;
- provider-scoped credentials;
- secure secret management;
- transactional outbox/inbox;
- evidence references;
- immutable audit trail;
- append-only ledger;
- provider reconciliation;
- fail-closed domain gates;
- private data/network boundaries.

## Follow-up

The next Technical documents define:

1. Domain Aggregate Boundaries;
2. State Machines and Transition Contracts;
3. Relational Data Model;
4. Ledger Posting Model;
5. API/Event Contracts.
