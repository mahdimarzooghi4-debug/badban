# Badban Security and Secrets Contract

- **Status:** Accepted
- **Date:** 2026-10-05
- **Stage:** Technical
- **Scope:** bounded external-lender pilot
- **Depends on:** System Context; Identity/RBAC Contract; Provider Adapter Contracts; Reconciliation Contract; Decision 0014

## 1. Objective

Define the minimum security architecture required to protect participant data, financial state, provider credentials, legal evidence, and privileged operations.

Core rule:

```
Security controls must preserve financial correctness, least privilege, auditability, and recoverability.
```

Security design must fail closed when a required trust control is unavailable or invalid.

## 2. Security Domains

The Technical security model covers:

1. identity and session security;
2. service/workload authentication;
3. provider integration security;
4. secrets and key management;
5. encryption in transit;
6. encryption at rest;
7. sensitive-data segregation;
8. application/API security;
9. network boundaries;
10. logging/audit protection;
11. backup/restore protection;
12. privileged operational access;
13. vulnerability and dependency controls;
14. incident response and credential containment.

## 3. Secret Classes

Badban secrets include:

- database credentials;
- provider API credentials;
- OAuth client secrets;
- mTLS private keys/certificates;
- webhook verification secrets;
- signing keys;
- encryption keys;
- broker credentials;
- object-storage credentials;
- privileged automation credentials.

Secrets must not be stored in:

- source code;
- Git history;
- ordinary application tables;
- logs;
- frontend bundles;
- static configuration committed to the repository.

## 4. Secret Storage

Runtime secrets must come from an approved secret-management mechanism.

Required properties:

- access-controlled retrieval;
- encryption at rest;
- audit logging;
- environment separation;
- rotation support;
- versioning;
- least-privilege access.

Domain records store only secret references/identifiers, never raw secret values.

## 5. Secret Access

A workload may access only the secrets required for its role.

Examples:

- lender adapter receives lender credentials only;
- reconciliation worker receives read-only provider credentials where possible;
- web frontend receives no provider or database secrets;
- outbox publisher receives broker credentials but not financial-admin credentials.

## 6. Secret Rotation

Every long-lived credential/key must support rotation.

Rotation workflow must:

- create/activate new secret version;
- support overlap where provider protocol requires it;
- revoke old version after validation;
- preserve audit history;
- avoid rewriting historical financial records.

If a provider does not support safe rotation, the provider readiness gate must record and mitigate that limitation before activation.

## 7. Key Separation

Cryptographic keys should be separated by purpose.

Examples:

- data encryption key;
- signing key;
- webhook verification key;
- backup encryption key;
- provider-client key.

One compromised key must not automatically expose every cryptographic function.

## 8. Encryption in Transit

All production traffic carrying authenticated, financial, legal, or participant data must use encrypted transport.

Requirements:

- TLS for client/API traffic;
- TLS/mTLS or equivalent secure transport for provider integrations where supported/required;
- encrypted database connections;
- encrypted broker/queue connections;
- encrypted object-storage access;
- no plaintext administrative protocols.

Certificate validation must not be disabled in production.

## 9. Encryption at Rest

At-rest encryption must cover, where technically applicable:

- transactional database storage;
- database backups/snapshots;
- object/evidence storage;
- message/broker persistence;
- secret store;
- exported reconciliation/accounting files;
- operational logs containing confidential metadata.

Encryption configuration must be environment-specific and controlled through infrastructure configuration.

## 10. Field-Level Protection

Highly sensitive fields may require stronger protection than general storage encryption.

Candidates include:

- national/legal identifiers;
- bank/account references;
- participant contact identifiers;
- sensitive legal/evidence references.

Technical design should support application-level encryption or tokenization where risk assessment requires it.

Search/index needs must not justify storing unnecessary plaintext.

## 11. Sensitive Data Segregation

Participant identity/profile data should be logically separated from financial transactional data where practical.

Financial tables should reference internal participant IDs rather than duplicate sensitive identity data.

This reduces propagation of PII across:

- ledger;
- audit;
- events;
- reconciliation;
- provider integration logs.

## 12. Data Minimization

APIs, events, logs, and provider payloads include only data needed for the specific business function.

Do not include full participant profiles in:

- domain events;
- provider events;
- generic audit records;
- operational telemetry.

Use stable references where possible.

## 13. Data Classification

Security handling follows at least these classes:

### RESTRICTED

- participant identity/legal identifiers;
- financial balances/account references;
- provider credentials;
- private keys;
- claim/legal evidence;
- authentication/session artifacts.

### CONFIDENTIAL

- risk policy;
- provider contract metadata;
- reconciliation details;
- internal operational controls.

### INTERNAL

- non-sensitive configuration;
- non-sensitive service metadata.

### PARTICIPANT_VISIBLE

Only explicitly approved fields in participant-facing read models.

Classification controls access, logging, export, and retention behavior.

## 14. API Security

All non-public APIs require authenticated identities unless explicitly designed as a public callback bootstrap endpoint with separate cryptographic verification.

Controls include:

- authentication;
- server-side authorization;
- input/schema validation;
- payload size limits;
- rate limiting where appropriate;
- idempotency enforcement;
- replay protection for signed callbacks;
- stable error handling without leaking secrets/internal stack traces.

## 15. Webhook Security

Inbound provider callbacks require:

1. provider identity validation;
2. signature/mTLS/OAuth verification as applicable;
3. timestamp/nonce validation where supported;
4. replay detection;
5. payload size/schema validation;
6. payload hash/evidence record;
7. inbox deduplication.

Invalid callbacks must not reach domain processing.

## 16. Replay Protection

Where provider protocol supports timestamp/nonce/signature semantics, inbound messages must reject:

- reused nonce;
- invalid timestamp window;
- duplicate external event ID;
- invalid signature.

Provider limitations must be documented and compensated with reconciliation and scope controls.

## 17. Session Security

Privileged human sessions require:

- MFA;
- short-lived tokens;
- configurable idle timeout;
- absolute session lifetime;
- revocation support;
- reauthentication/step-up for high-impact actions where supported.

Role revocation must invalidate future privileged actions promptly.

## 18. Token Security

Access tokens:

- are never logged;
- are not persisted in domain tables;
- use least-privilege scopes;
- have bounded lifetime;
- are validated for issuer/audience/signature/expiry.

Long-lived dynamic authorization truth must remain server-side, not solely inside tokens.

## 19. Browser Security

Web clients should use standard browser hardening controls, including:

- secure cookie settings where cookies are used;
- HttpOnly for session cookies;
- SameSite policy appropriate to the deployment;
- CSRF protection for cookie-authenticated mutations;
- content-security controls;
- no secrets in browser storage;
- no provider credentials in frontend code.

Exact framework implementation is selected later.

## 20. Network Segmentation

Logical deployment zones:

```
Public Edge
→ API / Web Tier
→ Private Application Tier
→ Private Data Tier
```

Provider callbacks terminate at controlled public integration endpoints.

Databases, brokers, secret stores, and internal admin interfaces must not be publicly exposed.

## 21. Outbound Egress Control

Provider integrations should use controlled outbound egress.

Where feasible:

- destination allowlists;
- provider-specific routes;
- mTLS/client identity;
- DNS/service allow rules;
- egress logging.

Application components without external-provider need should not receive unrestricted outbound network access.

## 22. Database Security

Database controls include:

- private network access;
- separate runtime/migration/admin identities;
- least-privilege grants;
- encrypted connections;
- audit of privileged access;
- no shared superuser credential in application runtime;
- restricted UPDATE/DELETE permissions on immutable financial/audit tables where practical.

## 23. Immutable Record Protection

Journal, audit, accepted valuation, provider event, and reconciliation observation history must be protected from ordinary runtime mutation.

Approaches may include:

- application permission boundaries;
- database grants;
- append-only constraints/triggers where appropriate;
- integrity hashes;
- backup/audit controls.

No operational admin UI may expose arbitrary edit/delete of these records.

## 24. Evidence Storage

Legal/financial evidence may be stored outside the relational database.

Requirements:

- opaque storage references;
- access control;
- encryption;
- content hash where appropriate;
- immutable or versioned retention behavior;
- audit of privileged reads/downloads where supported.

Evidence URLs must not be permanently public.

## 25. Logging Security

Logs must exclude:

- passwords;
- access/refresh tokens;
- private keys;
- raw provider secrets;
- complete sensitive documents;
- unnecessary national identifiers;
- full banking credentials.

Logs should include safe identifiers such as:

- correlation ID;
- aggregate ID;
- provider ID;
- event type;
- error/reason code;
- actor/service identity.

## 26. Audit Log Protection

Security-relevant audit events include:

- authentication failures;
- role/grant changes;
- maker-checker actions;
- policy activation;
- provider activation/suspension;
- secret/key rotation;
- break-glass access;
- journal reversal;
- reconciliation critical resolution;
- high-impact authorization denial.

Audit retention/immutability must meet later-approved legal/accounting retention requirements.

## 27. Break-Glass Security

Emergency privileged access requires:

- named identity;
- strong authentication;
- explicit reason;
- time-limited grant/session;
- elevated audit;
- post-event review;
- automatic expiry.

Break-glass cannot disable journal/audit capture or bypass hard legal/business invariants.

## 28. Administrative Access

Production infrastructure access should be separated from ordinary business-user access.

System operators may administer infrastructure but must not receive arbitrary application-level financial mutation permissions.

Direct production-database access should be exceptional, time-bounded, approved, and audited.

## 29. Backup Security

Backups must be:

- encrypted;
- access controlled;
- environment-scoped;
- integrity checked;
- restorable through tested procedures;
- protected from routine application credentials where possible.

Backup copies must not become an uncontrolled path around data-access policy.

## 30. Restore Security

Restore procedures must:

- use authorized operators;
- verify source backup integrity;
- preserve auditability;
- avoid accidentally restoring production secrets into non-production;
- support post-restore reconciliation/integrity validation.

A successful technical restore is not sufficient until key financial integrity checks pass.

## 31. Non-Production Data

Production participant/financial data should not be copied into development/test by default.

If production-derived data is ever required:

- approval;
- minimization;
- masking/pseudonymization;
- secure transfer;
- limited retention;
- restricted access

are mandatory.

Synthetic/test fixtures are preferred.

## 32. Environment Separation

At minimum, development/test/stage/production environments must have separate:

- secrets;
- provider credentials;
- databases;
- signing keys;
- storage buckets/containers;
- identity/client configuration.

Production credentials must never be usable from development.

## 33. Dependency Security

Implementation must support:

- pinned/controlled dependency versions;
- vulnerability scanning;
- dependency update workflow;
- software bill of materials where practical;
- removal of abandoned/high-risk dependencies;
- provenance controls for build artifacts.

Security findings are prioritized by exploitability and business impact.

## 34. Build and Artifact Integrity

Production deployables should be generated by controlled CI/CD.

Requirements:

- reproducible/traceable build metadata;
- immutable artifact identifier/digest;
- source commit linkage;
- dependency scan;
- artifact integrity verification before deployment.

Ad hoc developer-machine production builds are prohibited.

## 35. Configuration Integrity

Security-sensitive configuration must be versioned and reviewed.

Examples:

- authentication issuer/audience;
- provider endpoints;
- certificate references;
- rate limits;
- feature flags affecting financial paths;
- security headers;
- allowed callback origins.

Configuration changes require audit and environment promotion discipline.

## 36. Feature Flags

Feature flags must not create hidden bypasses around accepted Business/Technical gates.

Any feature flag that can:

- enable direct lending;
- bypass reconciliation;
- disable maker-checker;
- weaken provider/legal validation;
- skip ledger posting

is prohibited unless it is itself governed as a high-impact controlled configuration and approved for that environment.

Direct Lending remains disabled for the pilot.

## 37. Security Error Handling

Security failures should use stable reason codes without disclosing secret details.

Examples:

- `AUTHENTICATION_REQUIRED`;
- `AUTHORIZATION_DENIED`;
- `TOKEN_INVALID`;
- `SESSION_REVOKED`;
- `PROVIDER_AUTHENTICATION_FAILED`;
- `WEBHOOK_SIGNATURE_INVALID`;
- `REPLAY_DETECTED`;
- `SECRET_UNAVAILABLE`;
- `KEY_VERSION_INVALID`;
- `SECURITY_CONFIGURATION_INVALID`.

## 38. Fail-Closed Conditions

High-impact operations must fail closed when:

- identity cannot be verified;
- authorization state cannot be resolved;
- required secret/key unavailable;
- webhook/provider signature invalid;
- certificate validation fails;
- required encryption/security configuration invalid;
- maker-checker approval invalid;
- critical security dependency is unavailable and safe fallback does not exist.

## 39. Secret/Key Compromise Response

The architecture must support:

1. identify affected secret/key version;
2. disable/revoke compromised credential;
3. activate replacement;
4. rotate dependent credentials if required;
5. identify affected sessions/integrations;
6. review access/audit logs;
7. reconcile high-impact provider operations during compromise window;
8. preserve evidence.

Compromise response must not erase financial history.

## 40. Security Monitoring

Operational monitoring should include:

- authentication failure spikes;
- privileged role changes;
- repeated authorization denials;
- webhook signature failures;
- provider credential failures;
- secret retrieval failures;
- unusual break-glass use;
- unusual journal/reconciliation corrections;
- security configuration drift;
- expired/near-expiry certificates/credentials.

Thresholds are operational policy, not hard-coded universally.

## 41. Security Testing

Before production, security testing must cover:

- authentication/authorization bypass attempts;
- cross-program/entity/provider access;
- self-approval/maker-checker bypass;
- IDOR/resource-scope attacks;
- replayed provider callbacks;
- invalid signatures;
- expired/revoked tokens;
- secret leakage in logs/errors;
- insecure direct database access paths;
- privilege escalation;
- environment credential separation;
- backup/restore access controls.

## 42. Security Release Gate

A real-money pilot release must not proceed with unresolved Critical security findings affecting:

- authentication;
- authorization;
- secret/key exposure;
- provider trust;
- financial integrity;
- audit integrity;
- encryption;
- production data exposure.

Severity criteria and exception process must be documented in release governance.

## 43. Persistence / Configuration Additions

Technical implementation should support:

### secret_references

Metadata only:

- logical secret name;
- secret-store reference;
- environment;
- owning service/provider;
- active version reference;
- rotation metadata;
- no raw secret value.

### key_metadata

- key purpose;
- key-store/KMS reference;
- active version;
- activation/revocation timestamps;
- status;
- owner/service scope.

### security_events

Append-only security/audit events.

## 44. Hard Invariants

1. No raw secrets in source code, Git, browser bundles, ordinary DB rows, or logs.
2. Production secrets are environment-specific and least-privilege.
3. Sensitive transport is encrypted.
4. Sensitive storage/backups are encrypted.
5. Provider callbacks are authenticated before domain processing.
6. Participant/financial data is minimized across events/logs/integrations.
7. Production credentials are not reused in non-production.
8. Immutable financial/audit records cannot be arbitrarily edited by runtime users.
9. Break-glass is explicit, time-bounded, and audited.
10. Security failure never becomes a reason to guess or bypass a financial/legal control.

## 45. Next Technical Contracts

Next:

1. Observability and Operational Readiness Contract;
2. Deployment / Runtime Topology and Non-Functional Requirements;
3. Technical Stage Completion Review.
