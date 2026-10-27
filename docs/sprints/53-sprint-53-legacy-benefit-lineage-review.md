# Sprint 53 — Legacy Benefit Lineage Review

## Goal

Provide an auditable, two-person process for attaching verified program and participation-episode lineage to existing benefit records.

## Deliverables

- Governance-only queue for unlinked monthly pension and post-exit support records.
- Proposal includes the target record, proposed program/episode, evidence reference, and reason reference.
- API verifies the episode belongs to the participant and selected program.
- A different global governance approver can approve or reject with a recorded reason.
- Approval writes lineage to the source benefit record; rejection leaves it unchanged.
- Partial unique index prevents duplicate pending requests for one record.
- Reads and mutations are audited.

## Boundaries

- Do not infer or bulk-assign lineage.
- Evidence references support human review; they are not independently validated by the system.
- The queue does not return benefit amounts or national identifiers.
- No merge, Stage, release, or production operation is authorized.
