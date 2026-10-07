# Badban Sprints

- **Delivery State:** Sprint 03 Code + Code Review Complete; Stage Deferred; Sprint 04 Proposed
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

- [Sprint 14 — Reconciliation Engine Core](./14-sprint-14-reconciliation-engine-core.md) — **Code in progress; Decision 0039**
