# Sprint 18 — Recovery Verification Core

- **Status:** Accepted / Code Authorized
- **Date:** 2026-10-08
- **Stage:** Sprint
- **Scope:** backend-first / BL-050 core
- **Base Dependency:** Sprint 17 BL-049 Code + Code Review complete on PR #20
- **Branch Strategy:** stacked on `sprint-17-business-readiness-stop-controls`
- **Traceability:** Technical 12 §§29-30; Technical 13 §§30-31; Technical 14 §§18-20
- **Code Authorization:** GRANTED BY DECISION 0044

## Sprint Goal

Implement a provider-agnostic Recovery Verification Core that can verify restored Badban state after an authorized restore/rehearsal without inventing a backup vendor, restore transport, RPO/RTO target, or Production infrastructure.

## Authorized Verification Domains

The verifier may read and validate authoritative existing state for:

- database/application reachability;
- posted journal balance integrity;
- aggregate/version integrity where the repository already has versioned aggregates;
- outbox/inbox consistency;
- evidence-reference integrity at the metadata/reference level;
- RBAC/access-control integrity;
- reconciliation recoverability/readiness;
- active business stop controls during recovery;
- exact policy/provider/legal state needed for post-restore safety checks.

## Verification Semantics

Recovery verification is read-only with respect to financial/domain state.

It may produce verification evidence/results but must not:

- edit or repair Journal;
- mutate GuaranteeCase, ExternalLoanMirror, BackingAllocation, claims/recovery, provider lifecycle, policy lifecycle, reconciliation history, or Asset Positions;
- auto-clear stop controls;
- infer provider success;
- infer reconciliation MATCHED;
- treat process startup as recovery success.

A failed check remains explicit and blocks a successful recovery verification result.

## Restore Boundary

Sprint 18 does not perform infrastructure backup or restore.

The recovery core receives only explicit restore/rehearsal context supplied by an authorized operator or test harness, such as:

- restore/rehearsal reference;
- source backup reference;
- source integrity reference/digest where supplied;
- environment identifier;
- recovery correlation/reference.

The core verifies post-restore business integrity from Badban-owned authoritative state.

## RPO / RTO

No numeric RPO or RTO is introduced.

The model may carry approved RPO/RTO references or evidence fields later, but Sprint 18 must not invent target values or pass/fail thresholds.

## Journal Integrity

Verification must prove for every POSTED JournalEntry under the checked scope:

- debit total equals credit total exactly;
- postings reference the same JournalEntry;
- no PREPARED row is treated as a posted financial fact;
- reversal linkage remains structurally valid where present.

No synthetic balancing adjustment is permitted.

## Outbox / Inbox Integrity

Verification may prove structural consistency such as:

- outbox records required by persisted material events are present where the repository already defines that invariant;
- inbox identity/deduplication keys remain structurally unique;
- processed state is not silently inferred for unprocessed inbound messages.

The verifier must not publish, replay, or mutate messages as part of verification.

## Evidence Integrity

Sprint 18 validates evidence metadata/reference integrity only against Badban-owned persisted evidence metadata and hashes where available.

It must not claim object-storage bytes are valid unless an authoritative external/object-store verification source is actually supplied.

Missing external evidence verification remains explicit, never PASS by assumption.

## Access-Control Integrity

Verification may validate:

- referenced identities exist;
- active RoleGrant records have valid structural scope;
- privileged recovery verification itself requires accepted human operational/governance authorization;
- auditors remain read-only.

It does not redesign RBAC.

## Reconciliation Recoverability

The core may validate that:

- reconciliation tables and policy lineage are structurally readable;
- unresolved/stale/blocking cases remain visible;
- existing reconciliation state can be queried after restore;
- external re-establishment is not claimed until the required provider/reconciliation operation actually occurs.

No automatic reconciliation repair or MATCHED state is authorized.

## Business Stop Controls

Recovery verification must respect existing Sprint 17 operational stop controls.

A successful technical verification must not auto-clear active stop controls.

Resumption remains an explicit authorized action outside this verifier.

## Persistence / Evidence

Sprint 18 may add an append-only recovery-verification record and per-check result/evidence model if needed, provided it contains no secrets and does not duplicate financial truth.

A stored verification result must bind to:

- exact restore/rehearsal reference;
- checked source/context;
- verification version;
- actor;
- correlation;
- timestamps;
- individual check outcomes/evidence references.

## API / Test Harness

Authorized backend surface may expose an admin/operations-only recovery verification command and read endpoints for its evidence.

Tests must prove at minimum:

- balanced journals pass journal-integrity verification;
- an unbalanced/corrupted fixture fails closed;
- missing required evidence/reference fails closed;
- outbox/inbox verification is read-only;
- unresolved reconciliation remains visible after verification;
- active stop controls are preserved;
- auditor cannot execute verification mutation;
- verification never repairs financial/domain rows.

## Explicit Non-Goals

No backup vendor, backup schedule, object-storage provider, restore transport, secret restoration implementation, Production DR orchestration, DNS/TLS, infrastructure provisioning, RPO/RTO numeric target, provider restart command, message replay command, direct DB repair, Stage/QA/Release/Production, or real-money behavior.

## Delivery Boundary

Sprint 18 ends at Code + Code Review for the BL-050 Recovery Verification Core.

PR must remain Draft/Open and stacked on Sprint 17 until prerequisites are explicitly merged in order. Merge requires explicit user authorization.
