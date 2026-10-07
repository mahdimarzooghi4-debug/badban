# Sprint 12 — Audit and Evidence Trace

- **Status:** Accepted
- **Date:** 2026-10-07
- **Stage:** Sprint Planning
- **Scope:** control-plane hardening
- **Entry Gate:** Sprint 11 / BL-041 merged; post-merge CI #258 green
- **Depends on:** BL-004; BL-006; Technical 01; Technical 04; Technical 12
- **Code Authorization:** GRANTED BY DECISION 0037

## 1. Sprint Goal

Complete **BL-044 — Audit and Evidence Trace** on the existing AuditEvent / EvidenceReference foundation.

The Sprint must make audit history append-only at the database boundary, preserve applicable correlation/policy/evidence lineage, and ensure generic audit/evidence metadata never becomes a secret/raw-content sink.

## 2. Audit Event Integrity

AuditEvent history is immutable after insert.

Database protection must reject ordinary runtime:

- UPDATE;
- DELETE.

Existing append-only insert behavior remains.

No generic audit edit/delete API is introduced.

## 3. Audit Lineage

The shared audit primitive must support the accepted AuditEvent lineage fields:

- aggregate type/id/version;
- action;
- actor type/id;
- correlation ID;
- causation ID when available;
- reason code when available;
- policy pack ID when applicable and already known;
- evidence reference when applicable and already known;
- outcome;
- safe previous/new state;
- safe scope;
- occurrence time.

Missing lineage must not be guessed.

## 4. Audit Payload Safety

Generic audit previous/new-state and scope payloads must fail closed when they contain fields whose purpose is to carry:

- passwords;
- access/refresh/session tokens;
- client/provider secrets;
- private/signing keys;
- authorization headers/cookies;
- raw provider payloads;
- complete evidence/document/blob content.

Safe identifiers and references are permitted.

Validation is recursive for nested mappings/lists.

The implementation must not log the rejected sensitive value.

## 5. Evidence Reference Metadata

Complete the accepted Technical 04 EvidenceReference metadata shape where currently missing, including:

- source legal entity reference when available;
- verification-status field;
- captured-at time.

Evidence content itself remains outside the relational record.

## 6. Evidence Registration Primitive

Provide an internal application primitive to register evidence metadata.

Requirements:

- evidence type required;
- storage provider required;
- opaque storage reference required;
- permanent public HTTP(S) URLs are rejected as storage references;
- optional external reference;
- optional content hash;
- optional media type;
- optional source legal entity;
- optional verification status;
- explicit captured-at time;
- no provider credentials or raw evidence content accepted by the primitive.

No public upload/download API is authorized.

## 7. Evidence History Protection

Evidence metadata that identifies the underlying evidence object must not be silently rewritten.

Database protection must reject ordinary UPDATE/DELETE of existing EvidenceReference rows.

Corrections/replacement require a new reference in a later authorized workflow rather than rewriting historical evidence identity.

## 8. Existing Producer Hardening

Existing material audit producers may be updated only where already-available lineage can be attached safely.

Examples:

- portfolio-risk audit may attach the policy pack already used for the evaluation;
- legal-authorization audit keeps its evidence reference;
- journal audit keeps correlation/causation and existing safe references where available.

No missing policy or evidence reference is inferred.

## 9. Tests

Tests must prove:

- AuditEvent UPDATE/DELETE rejected by database;
- EvidenceReference UPDATE/DELETE rejected by database;
- safe audit payload accepted;
- nested secret/raw-content keys rejected before persistence;
- rejected values do not appear in persisted audit rows;
- causation/policy/evidence lineage is persisted when supplied;
- evidence registration rejects public HTTP(S) storage URLs;
- evidence registration stores metadata only;
- no generic audit/evidence mutation API is introduced;
- existing material command tests remain green.

## 10. Explicit Non-Goals

No BL-020, BL-033, BL-042, provider adapter, reconciliation workflow, evidence-content storage, evidence download, secret rotation implementation, retention-period decision, Stage pass, QA pass, Release Approval, Production, or real-money behavior.

## 11. Definition of Done

BL-044 is Done through Code Review when database immutability, safe audit payload validation, accepted audit lineage support, evidence metadata completion/registration, and regression tests are complete and full CI is green.
