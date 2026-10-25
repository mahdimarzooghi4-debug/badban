# Badban Sprints

- **Delivery State:** Sprints 01–39 merged; Sprint 40 Code in progress (Decision 0058); Stage deferred
- **Scope:** bounded external-lender pilot defined by Decision 0016
- **Stage Environment:** currently unavailable / deferred by Decision 0023
- **Real-Money / Production Authorization:** NOT GRANTED

## Parent delivery process

**Business ✓ → Technical ✓ → Scrum/Product Backlog ✓ → Sprint → Code → Code Review → Stage → QA/Testing → Release Approval → Production → Monitoring → Improvement**

Decision 0023 defers execution of the Stage gate while the environment is unavailable. It does not remove the Stage requirement.

Reviewed Sprint outputs merged to `main` accumulate into the future Stage candidate.

## Completed Sprints

- [Sprint 01 — Implementation Foundation](./01-sprint-01-implementation-foundation-plan.md) — **Accepted / Code + Code Review Complete**
- [Sprint 02 — Identity and Core Participant / Asset State](./02-sprint-02-identity-core-participant-asset-state.md) — **Completed / Code + Code Review Complete**
- [Sprint 03 — Control, Valuation, and Journal Foundations](./03-sprint-03-control-valuation-journal-foundations.md) — **Completed / Code + Code Review Complete**

### Sprint 01 scope

- BL-001 Implementation Stack Decision Pack
- BL-002 Repository and CI Quality-Gate Blueprint
- BL-003 Environment, Configuration, and Secret Boundary
- BL-004 Transactional Persistence and Migration Foundation
- BL-005 Observability and Correlation Foundation

Relevant gates:

- Decision 0020 — Initial Implementation Stack — **Accepted**
- Decision 0021 — Sprint 01 Code Authorized — **Accepted**
- Decision 0022 — Sprint 01 Code Review Complete; Stage Not Yet Authorized — **Accepted**

### Sprint 02 scope

- BL-006 Central Identity Integration
- BL-007 RBAC and Scoped Authorization Engine
- BL-009 Program and Participation Episode
- BL-010 Asset Type Registry
- BL-011 Asset Position and Ownership/Funding Classification
- BL-044 Audit and Evidence Trace baseline

Relevant gates:

- Decision 0024 — Sprint 02 Code Authorization — **Accepted**
- Decision 0025 — Sprint 02 Code Review Complete; Stage Still Deferred — **Accepted**

## Dependency Note Before Sprint 03

The Product Backlog candidate Slice 2 cannot be taken as-is:

- BL-013 depends on BL-008 Maker-Checker, which is not yet Done;
- BL-032 depends on BL-030 Journal Engine in addition to policy/capacity items.

Therefore Sprint 03 planning must select only currently Ready dependency-unblocking work rather than bypass those prerequisites.

## Scope Guard

Direct Lending remains outside scope.

Sprint development while Stage is deferred does not grant QA/Testing, Release Approval, Production, provider-production certification, or real-money activation.

## Sprint 03 completion

Sprint 03 scope:

- BL-008 Maker-Checker / ApprovalRequest
- BL-012 Immutable Valuation Observation
- BL-030 Append-Only Journal Engine

Relevant gates:

- Decision 0026 — Sprint 03 Code Authorization — **Accepted**
- Decision 0027 — Sprint 03 Code Review Complete; Stage Still Deferred — **Accepted**

Sprint 04 planning is now Proposed from the accepted Product Backlog and satisfied dependencies.


## Current Sprint Planning

- [Sprint 04 — Policy Lifecycle and Deterministic Resolution](./04-sprint-04-policy-lifecycle-deterministic-resolution.md) — **Proposed**

Proposed Sprint 04 scope:

- BL-013 Policy Version and Policy Pack Lifecycle
- BL-014 PolicyResolver and DecisionSnapshot

Decision 0028 — Sprint 04 Code Authorization — **Proposed**

Sprint 04 Code is not yet authorized.

## Sprint 14

- [Sprint 14 — Reconciliation Engine Core and Lender Baseline](./14-sprint-14-reconciliation-engine-core.md) — **Accepted / Code Authorized**
- Decision 0040 authorizes BL-042 Core + lender reconciliation vertical slice only.
- BL-043 resolution/block workflow remains out of scope.
- Decision 0033 keeps Stage available, but backend-first strategy means Stage is not automatically run after this Sprint.

## Sprint 36

- [Sprint 36 — Verified Source Acquisition Boundary](./36-sprint-36-verified-source-acquisition.md) — **Merged to main via PR #40; CI #492 passed**
- Decision 0054 authorizes only a read-only acquisition and verification boundary for explicitly registered sources.
- No new source integrations, database writes, comparison rules, or financial behavior are authorized by this Sprint.

## Sprint 37

- [Sprint 37 — Internal Posted-Journal Source](./37-sprint-37-internal-posted-journal-source.md) — **Merged to main via PR #44; CI #495 and combined CI #510 passed**
- Decision 0055 authorizes only read-only source extraction from actual posted journal facts, with exact Program and Legal Entity lineage.
- External sources without an identified authority remain unavailable; BL-020 remains blocked on explicit policy inputs.

## Sprint 38

- [Sprint 38 — Internal Asset Inventory Source](./38-sprint-38-internal-asset-inventory-source.md) — **Merged to main via PR #44; CI #498 and combined CI #510 passed**
- Decision 0056 authorizes a program-scoped, read-only snapshot of Badban's own persisted asset positions.
- The internal snapshot remains distinct from custody and collateral-registry evidence; no comparisons or financial outcomes are included.

## Sprint 39

- [Sprint 39 — Internal Valuation Observation Source](./39-sprint-39-internal-valuation-observation-source.md) — **Merged to main via PR #45; exact-head CI #508 and post-merge main CI #512 passed**
- Decision 0057 authorizes preserving recorded valuation observations and freshness labels as internal stored facts only.
- No provider verification, freshness determination, valuation selection, or financial outcome is included.


## Status reconciliation — 2026-10-25

The historical Sprint 04 proposal above was superseded by later accepted Sprint plans and delivery. Sprints 36–39 and their source acquisitions are merged to `main` (PRs #40, #44, #45; post-merge CI #512 green). The 2026-10-25 dossier addendum records the present BL-020 decision gates. No new Sprint has been authorized by this status correction; Stage, QA, Release Approval, and Production remain separate gates.


## Sprint 40

- [Sprint 40 — Configurable Multi-Source Evidence Registry](./40-sprint-40-configurable-external-source-registry.md) — **Code in progress; Decision 0058 authorizes bounded scope**
- BL-053 defines a provider-neutral, versioned source registry and read-only multi-source acquisition by evidence purpose and asset type.
- No live sources are selected or connected. Conflicting/stale/unavailable evidence fails closed; valuation selection and reservation behavior remain out of scope.

## Sprint 44

- [Sprint 44 — Automatic Applicant Identity Link](./44-sprint-44-automatic-applicant-identity-link.md) — **Code in progress; Decision 0062 authorizes bounded scope**
- Resolves a verified OIDC `national_id` claim to one participant record without asking the applicant to select or enter a record, and does not return the national ID.
- The external identity provider must issue the claim after its participant identity checks; applicant financial summaries remain the next BL-057 slice.
