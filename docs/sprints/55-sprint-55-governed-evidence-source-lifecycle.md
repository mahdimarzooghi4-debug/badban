# Sprint 55 — Governed External Evidence Source Lifecycle

## Goal

Complete maker-checker activation and suspension for the multi-source registry while keeping unknown providers unavailable.

## Deliverables

- Add auditable lifecycle review requests for ACTIVATE and SUSPEND actions.
- Require an independent global governance approver to approve or reject each request.
- Permit only valid source-state transitions and one pending lifecycle review per source.
- Expose lifecycle review history through the existing external evidence registry API.
- Advertise source management capability in the role-derived admin workspace.
- Add the migration and Decision 0073.

## Boundaries

- Do not connect a live source or install provider credentials.
- Do not select a valuation result or establish freshness/risk thresholds.
- Do not enable guarantee reservation or any financial mutation.
- No merge, Stage, release, or production operation is authorized.
