# Badban Sprints

- **Delivery State:** Sprint 02 Accepted — Code Authorized; Stage Deferred
- **Scope:** bounded external-lender pilot defined by Decision 0016
- **Stage Environment:** currently unavailable / deferred by Decision 0023
- **Real-Money / Production Authorization:** NOT GRANTED

## Parent delivery process

**Business ✓ → Technical ✓ → Scrum/Product Backlog ✓ → Sprint → Code → Code Review → Stage → QA/Testing → Release Approval → Production → Monitoring → Improvement**

Decision 0023 defers execution of the Stage gate while the environment is unavailable. It does not remove the Stage requirement.

Reviewed Sprint outputs merged to `main` accumulate into the future Stage candidate.

## Completed Sprint

- [Sprint 01 — Implementation Foundation](./01-sprint-01-implementation-foundation-plan.md) — **Accepted / Code + Code Review Complete**

Sprint 01 scope:

- BL-001 Implementation Stack Decision Pack
- BL-002 Repository and CI Quality-Gate Blueprint
- BL-003 Environment, Configuration, and Secret Boundary
- BL-004 Transactional Persistence and Migration Foundation
- BL-005 Observability and Correlation Foundation

Relevant gates:

- Decision 0020 — Initial Implementation Stack — **Accepted**
- Decision 0021 — Sprint 01 Code Authorized — **Accepted**
- Decision 0022 — Sprint 01 Code Review Complete; Stage Not Yet Authorized — **Accepted**

## Current Sprint Planning

- [Sprint 02 — Identity and Core Participant / Asset State](./02-sprint-02-identity-core-participant-asset-state.md) — **Accepted / Active**

Proposed Sprint 02 scope:

- BL-006 Central Identity Integration
- BL-007 RBAC and Scoped Authorization Engine
- BL-009 Program and Participation Episode
- BL-010 Asset Type Registry
- BL-011 Asset Position and Ownership/Funding Classification
- BL-044 Audit and Evidence Trace baseline

## Sprint 02 Gate

Decision 0024 is **Accepted**. Code is authorized only for the selected Sprint 02 scope.

## Scope Guard

Sprint work must remain inside the bounded external-lender pilot.

Direct Lending remains outside scope.

Sprint development while Stage is deferred does not grant QA/Testing, Release Approval, Production, provider-production certification, or real-money activation.
