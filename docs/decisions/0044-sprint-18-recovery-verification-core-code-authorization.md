# Decision 0044 — Sprint 18 Recovery Verification Core; Code Authorization

- **Status:** Accepted
- **Date:** 2026-10-08
- **Scope:** Sprint 18 / BL-050 Recovery Verification Core / Code Authorization
- **Depends on:** BL-004; BL-041; BL-042; BL-049; Technical 12 §§29-30; Technical 13 §§30-31; Technical 14 §§18-20
- **Authorizes:** BL-050 provider-agnostic post-restore verification core only

## Decision

Authorize Code for a read-only, fail-closed Recovery Verification Core that verifies Badban business integrity after an externally performed authorized restore/rehearsal.

This decision does not authorize an infrastructure backup system, restore transport, Production disaster-recovery orchestration, or any provider-specific operational integration.

## Verification Domains

The core may verify authoritative persisted state for:

- application/database reachability;
- Journal integrity;
- versioned aggregate integrity where already modeled;
- outbox/inbox structural consistency;
- evidence metadata/reference integrity;
- RBAC/access-control integrity;
- reconciliation recoverability/readability;
- active operational stop controls;
- policy/provider/legal state required for post-restore safety.

## Read-Only Recovery Invariant

Recovery verification must not mutate or repair authoritative financial/domain state.

It must never directly modify:

- JournalEntry or JournalPosting;
- GuaranteeCase;
- BackingAllocation;
- ExternalLoanMirror;
- claim/recovery state;
- AssetPosition;
- CreditProvider or AssetType lifecycle;
- PolicyVersion lifecycle;
- ReconciliationCase/Observation/Block history;
- Inbox/Outbox delivery state;
- existing obligations.

Detected inconsistency is reported; it is not silently repaired.

## Restore Context

Execution requires an explicit restore/rehearsal reference supplied by an authorized caller/test harness.

Optional source metadata may include explicit backup/integrity references, but the verifier must not fabricate them.

No successful result may claim that external backup bytes, secret restoration, provider restart, or object-storage content were verified unless authoritative evidence for that check was actually supplied.

## Journal Check

For POSTED journals in scope:

- debit and credit totals must balance exactly;
- POSTED state must remain structurally coherent with postings;
- PREPARED state is not accepted as a posted financial fact;
- reversal linkage must remain structurally valid.

No balancing adjustment or compensating journal is created by the verifier.

## Outbox / Inbox Check

The verifier may perform read-only consistency checks against the existing BL-041 data model.

It must not:

- publish outbox messages;
- mark them delivered;
- replay inbox messages;
- infer processing success from silence;
- alter deduplication state.

## Evidence Check

Only persisted evidence metadata/hash/reference integrity may be verified internally.

External object-storage integrity remains UNKNOWN/NOT VERIFIED unless an authoritative external result is provided.

Missing external verification is never converted to success.

## Access-Control Check

Recovery verification execution is human-controlled through existing RBAC.

Accepted operational/governance roles may execute; auditors may read evidence but remain unable to initiate verification mutation.

No new identity system or break-glass bypass is authorized.

## Reconciliation Check

The verifier must preserve visibility of unresolved, stale, disputed, and blocking reconciliation state.

It may prove that reconciliation state/policy lineage is structurally readable after restore.

It must not auto-run corrective reconciliation, mark cases MATCHED/RESOLVED, or clear reconciliation blocks.

## Stop-Control Check

Active Sprint 17 stop controls remain authoritative during and after verification.

A successful technical verification does not auto-clear a stop control and does not authorize business resumption.

## Verification Evidence

An append-only verification record and child check records may be added.

Any such record must bind to:

- restore/rehearsal reference;
- verification schema/version;
- actor;
- correlation;
- timestamps;
- individual check result;
- source/evidence reference where applicable.

No secrets or raw sensitive evidence content may be persisted.

## RPO / RTO

No numeric RPO or RTO target is authorized.

The system may later reference approved targets, but Sprint 18 must not create default recovery objectives or infer compliance.

## Explicit Non-Goals

No backup vendor, backup schedule, backup encryption implementation, restore engine, object-storage provider, secret/key restoration implementation, provider restart, message replay, infrastructure provisioning, DNS/TLS, Production DR automation, RPO/RTO target, direct repair, UI/Figma/frontend, Stage, QA Gate completion, Release, Production, or real-money behavior.

## Approval Effect

Code is authorized only for the Sprint 18 Recovery Verification Core defined above.

Sprint 18 remains stacked on Sprint 17. Any PR must remain Draft/Open through Code Review and must not merge ahead of prerequisite PRs or without explicit user instruction.
