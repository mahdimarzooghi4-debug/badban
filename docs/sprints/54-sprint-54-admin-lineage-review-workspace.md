# Sprint 54 — Admin Legacy Benefit Lineage Review Workspace

## Goal

Make the existing governance-only legacy benefit lineage queue discoverable in the admin workspace index.

## Deliverables

- Add a dedicated `ADMIN_BENEFIT_LINEAGE_REVIEW` workspace entry.
- Show it only for an active global `ROLE_GOVERNANCE_APPROVER` grant.
- Advertise queue read, request, approve, and reject capabilities.
- Preserve independent authorization and maker-checker checks on every queue endpoint.
- Document the discovery contract in Decision 0072.

## Boundaries

- Do not add a UI client or change the review API in this Sprint.
- Do not grant permissions through workspace metadata.
- No merge, Stage, release, or production operation is authorized.
