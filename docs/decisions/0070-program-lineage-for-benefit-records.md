# Decision 0070 — Program Lineage for Benefit Records

- **Status:** Code authorized to attach monthly pension and post-exit support records to a verified participant episode and program.
- **Authority:** The source plan defines beneficiary financial cases with monthly pension, post-exit support, and return allocation facts; current Badban access is program scoped.
- **Scope:** Sprint 52 lineage migration, write validation, funding-source scope, and supporting-institution read model.

## Decision

New monthly pension entitlements and post-exit cases must identify a participant, program, and participation episode that belong together. The database enforces this relationship with a composite foreign key. Authorized support institution readers may see only financial service records matching the exact participant and episode in their granted program.

Already-posted support return allocations may be summarized only by participant, program, and currency because the journal postings currently carry program and participant scope but no episode identifier.

## Legacy records

Existing benefit records receive nullable lineage fields and remain unlinked. They are not assigned to a program or episode by inference. They stay out of program-scoped support views until lineage is verified and provided through an approved process.

## Boundaries

- No national ID or contact details are introduced into this view.
- Return allocations are labeled as participant/program level, not episode-level profit.
- No service approval, payout, enrollment, merge, Stage, release, or production action is authorized.
