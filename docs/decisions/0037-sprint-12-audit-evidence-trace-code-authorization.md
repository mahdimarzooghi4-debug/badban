# Decision 0037 — Sprint 12 Audit and Evidence Trace; Code Authorization

- **Status:** Accepted
- **Date:** 2026-10-07
- **Scope:** Sprint 12 / Audit and Evidence Trace / Code Authorization
- **Depends on:** BL-004; BL-006; Technical 01; Technical 04; Technical 12; post-merge CI #258 green
- **Authorizes:** BL-044 only

## Decision

Accept Sprint 12 and authorize Code only for:

- **BL-044 — Audit and Evidence Trace**

## Rationale

Badban already records many material actions through the shared audit primitive and already stores evidence metadata references. The remaining accepted control gap is to harden these records so audit history cannot be rewritten, evidence metadata remains opaque and non-secret-bearing, and material audit entries preserve the applicable correlation / policy / evidence lineage without copying restricted raw content.

BL-044 is P1 and its dependencies are complete. It can be completed without inventing unresolved provider, reservation, settlement, retention-duration, or UI contracts.

## Authorized Scope

Sprint 12 may implement:

- database protection that rejects ordinary UPDATE/DELETE of audit events;
- database protection for evidence metadata history where immutable history is required;
- completion of EvidenceReference persistence fields already specified by Technical 04 where missing;
- an internal evidence-metadata registration primitive that stores references/metadata only and never provider credentials or evidence content;
- validation that evidence storage references are opaque/non-public references rather than permanent public URLs;
- safe-audit validation that rejects secret-bearing or raw restricted-content fields from generic audit previous/new-state/scope payloads;
- shared audit support for causation and applicable policy-pack/evidence references already present in the accepted AuditEvent contract;
- updates to existing material audit producers where an already-available policy/evidence reference should be attached;
- tests proving append-only behavior, lineage capture, secret/raw-content rejection, and absence of generic evidence-content exposure.

## Evidence Boundary

This Sprint stores evidence **metadata and opaque references only**.

It does not:

- store raw legal/financial evidence in ordinary relational fields;
- invent an object-storage provider;
- create public/presigned evidence URLs;
- create an evidence-download API;
- invent retention periods;
- invent access-control roles beyond the already accepted authorization model.

Privileged evidence-content access remains a later authorized capability and must itself be audited where supported.

## Audit Payload Boundary

Generic audit payloads may contain safe identifiers, state names, reason codes, version references, and business values required to explain the transition.

They must not contain raw secrets, credentials, tokens, private keys, raw provider payloads, complete document content, or equivalent restricted blobs.

If unsafe generic audit content is attempted, the write must fail closed rather than silently persist it.

## Historical Integrity

Audit events are historical facts.

Ordinary runtime mutation or deletion of an existing audit event is forbidden.

Evidence metadata created as historical evidence references must not be silently rewritten into a different underlying evidence object.

No generic admin edit/delete API is authorized for audit or evidence history.

## Existing Audit Producers

Sprint 12 may harden existing audit producers only where doing so preserves already accepted business behavior.

It must not introduce new business transitions or infer missing policy/evidence lineage.

When an applicable policy/evidence reference is not available from the authorized command context, the implementation must not guess one.

## Explicit Non-Goals

No BL-020, BL-033, BL-042, reconciliation workflow, provider adapter, secret rotation capability, evidence-content storage, evidence-download UI/API, Stage pass, QA pass, Release Approval, Production, or real-money behavior.

## Approval Effect

Code is authorized only for BL-044 within the Sprint 12 boundary.
