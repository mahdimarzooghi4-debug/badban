# Decision 0069 — Supporting Institution Financial Case

- **Status:** Code authorized for a read-only financial case under exact program-scoped support institution access.
- **Authority:** Owner direction that Badban's three services need distinct individual, administrator, and lender workspaces, plus the source document's requirement for beneficiary-level financial case records.
- **Scope:** Sprint 51 endpoint for one participant episode in one program.

## Decision

An authenticated supporting institution operator may read a beneficiary financial case only when the operator has an active grant for the exact program and the supplied participant episode belongs to that participant and program. The view may include program-attributed asset positions, source-stamped valuation observations, guarantee case amounts and status, and linked provider-reported loan status and outstanding principal.

## Boundaries

- Participant and episode identifiers are internal references; national ID and contact details are not returned.
- Valuation observations retain their source and freshness metadata and are not represented as selected/current quotes.
- Guarantee exposure and lender-reported outstanding principal remain separate values.
- Profit share, monthly pension, and post-exit support are not returned because current records lack the required program lineage or allocation basis.
- This read-only view does not enroll a participant, grant a guarantee, approve a service, or change a financial record.
- No merge, Stage, release, or production operation is authorized.
