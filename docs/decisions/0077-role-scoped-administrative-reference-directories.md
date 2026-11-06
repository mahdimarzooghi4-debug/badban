# Decision 0077 — Role-Scoped Administrative Reference Directories

- **Status:** Code authorized for bounded, read-only administrative reference directories.
- **Authority:** Existing role-governed admin workspace (Decision 0068), central identity and role-grant foundation (BL-006), program foundation (BL-009), and existing provider/program read authorization contracts.
- **Scope:** Sprint 64 only.

## Decision

Badban may expose three separate administrative reference directories, each derived from existing persisted records and guarded by the role and scope already used by adjacent approved read contracts:

1. **Human Identity Directory** — only an active global ROLE_GOVERNANCE_APPROVER may list human identities (STAFF, GOVERNANCE, AUDITOR) for grant administration. Responses contain only identity UUID, identity type, status, and creation time.
2. **Legal Entity Directory** — active global ROLE_GOVERNANCE_APPROVER, ROLE_LEGAL_COMPLIANCE, or ROLE_AUDITOR may list legal-entity reference metadata. Responses contain legal-entity UUID, legal name, entity type, status, version, and creation time.
3. **Program Directory** — active global ROLE_GOVERNANCE_APPROVER, ROLE_AUDITOR, or ROLE_OPERATIONS may list program reference metadata. Responses contain program UUID, code, name, status, linked legal-entity UUID (nullable), version, and creation time.

Each endpoint uses the existing human-only authorization engine, exact GLOBAL scope, bounded pagination, deterministic ordering, and append-only read audit. The AdminWorkspaceIndex advertises a directory only when the caller has the corresponding active global role; the directory endpoint independently enforces that same authorization.

## Explicit privacy and domain boundaries

- Identity responses must not expose external_subject, OIDC claims, national ID, contact data, or identity credentials. Participant and service identities are not part of this directory.
- Legal-entity responses must not expose registration_identifier, legal-authorization identifiers/evidence, contacts, or financial records.
- Program responses must not expose beneficiary records, participant counts, eligibility, participation, balances, or financial outcomes.
- There is **no global participant/beneficiary directory**. Individual beneficiary data remains available only through the already-approved exact-program support-institution workspace; applicant service requests remain available only through exact service-scoped queues.
- These are reference read models only. No create/update/delete, role grant, enrollment, eligibility, legal verification, provider activation, financial command, or state transition is added.
- UI capability visibility is discovery metadata only; every backend route continues to authorize independently.

## Non-goals

- No identity-provider search or external directory integration.
- No personal names, email addresses, phone numbers, or national identifiers are inferred or fabricated.
- No organization creation or legal-entity lifecycle policy is introduced.
- No Stage, QA admission, release approval, Production, or real-money authorization is granted.
