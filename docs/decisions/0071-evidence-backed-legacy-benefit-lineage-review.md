# Decision 0071 — Evidence-Backed Legacy Benefit Lineage Review

- **Status:** Code authorized for a governance-only maker-checker workflow to connect unlinked legacy benefit records.
- **Authority:** Sprint 52 left legacy benefit records unlinked because their program and participant episode cannot be inferred safely.
- **Scope:** Sprint 53 review queue and assignment for monthly pension entitlements and post-exit support cases.

## Decision

A global governance approver may submit a legacy benefit record with a proposed program and participation episode, plus an evidence reference and reason reference. The service verifies the proposed episode belongs to the benefit record's participant and selected program. Another global governance approver must approve or reject the request and record a decision reference.

Approval writes the verified program and episode to the benefit record. Rejection leaves the record unlinked. The review request and decision are auditable; at most one pending request may exist for a benefit record.

## Boundaries

- No mapping is created automatically and no identifier is guessed.
- The evidence is referenced, not treated as verified by software; the designated approvers remain responsible for checking it.
- The workflow does not expose amounts or identity details in its queue.
- No service approval, payout, enrollment, merge, Stage, release, or production action is authorized.
