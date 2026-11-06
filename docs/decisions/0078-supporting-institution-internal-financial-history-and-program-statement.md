# Decision 0078 — Supporting Institution Internal Financial History and Program Statement

- **Status:** Accepted — owner approval recorded 2026-11-06.
- **Scope:** Read-only supporting-institution program financial history and program statement.
- **Related decisions:** 0015 (Accounting and Financial Sub-Ledger Model), 0055 (Internal Posted-Journal Source), 0066 (Supporting Institution Workspace), 0069 (Supporting Institution Financial Case), 0070 (Program Lineage for Benefit Records).

## Context

Badban is not connected to a bank or payment provider. The supporting-institution workspace currently has:
- a program list guarded by an active exact-program role grant;
- a program beneficiary list;
- a read-only financial case for one beneficiary episode in one program;
- an internal append-only double-entry journal and a program-scoped, read-only source adapter over POSTED journal rows.

The internal journal source is currently an application/reconciliation source, not a public supporting-institution API. The existing finance-journal API is restricted to finance-reconciliation/auditor roles at legal-entity scope. No supporting-institution program-level financial-history or program-statement endpoint currently exists.

## Accepted decision

Authorize a bounded, read-only, exact-program view of Badban's own posted journal records for the supporting-institution operator. This is an internal Badban ledger view, not a bank statement and not proof of external settlement.

### 1. Authorization and scope

- Only a human identity with an active, unexpired `ROLE_SUPPORT_INSTITUTION_OPERATOR` grant for the exact `SCOPE_PROGRAM` may read the selected program.
- The program must remain ACTIVE and linked to its legal entity.
- The path `program_id` is the only program selector. Callers cannot widen the scope with a legal-entity, participant, owner, or global filter.
- Every read is audited. Authorization is rechecked by each endpoint; frontend visibility is not authorization.
- No cross-program roll-up or legal-entity-wide access is introduced.

### 2. Financial history

Accepted endpoint:

`GET /api/v1/support-institution/programs/{program_id}/financial-history`

- Read only `POSTED` journal entries with a non-null posting timestamp and postings for the exact program and its linked legal entity.
- Return only complete journal entries whose postings all belong to the requested program and linked legal entity. Mixed-program or otherwise out-of-scope entries are omitted rather than exposing another program's lines or presenting an unbalanced partial journal.
- Preserve the journal's currency and the posting account, debit/credit amounts, account normal-balance, and ledger-layer classification.
- Preserve safe event timestamps and source/evidence references needed for traceability. Do not expose actor identity, free-form private text, unrelated program identifiers, or unrelated posting lines.
- Corrections remain visible as immutable reversal/compensating entries; original posted entries are never rewritten.
- Label every row as an internal Badban journal posting. A journal row or optional settlement reference alone must not be represented as a confirmed bank transfer, payment, receipt, or cash movement.
- No `PREPARED` or unposted entry is visible. Missing posted evidence is `SOURCE_UNAVAILABLE`, not an assumed zero or a fabricated empty financial history.

### 3. Program statement

Proposed endpoint:

`GET /api/v1/support-institution/programs/{program_id}/financial-statement`

- Derive the statement only from the accepted internal posted-journal source in Decision 0055, under the exact program scope.
- Preserve separate rows by account code, currency, linked legal entity, economic-owner type, ledger layer, and normal-balance classification.
- Do not combine currencies, account classes, legal entities, owner classes, or ledger layers into a single total. Do not perform FX conversion.
- Keep `MONETARY`, `MEMORANDUM_CONTROL`, and `EXTERNAL_MIRROR` records visibly distinct. Memorandum/control and external-mirror records are not cash and must never be added to monetary cash or owner-balance totals.
- Do not expose participant names, national identifiers, contact details, or participant-level balances in this aggregate view. Beneficiary drill-down remains through the existing exact-program, exact-episode financial-case endpoint.
- Include source snapshot time, source contract/mapping version, content hash, and evidence-reference lineage. No posted evidence returns `SOURCE_UNAVAILABLE`, never zero.

### 4. Explicit exclusions

This proposal does not authorize or imply:
- bank, payment-gateway, custodian, lender, guarantee-issuer, or settlement-provider connectivity;
- payment, deposit, withdrawal, transfer, funding request, payout, receipt, reconciliation mutation, or any other financial command;
- a claim that an internal journal posting proves an external movement of money;
- a cross-program or global institution roll-up;
- participant counts, program performance/ROI, guaranteed returns, consolidated capital totals, or other KPIs without separately approved metric definitions;
- aggregation of asset quantities with monetary balances or valuation observations;
- treating external loan mirrors, guarantee exposure, memorandum accounts, or unverified valuation observations as cash;
- new authorization roles, broader role grants, or changes to the existing financial ownership rules.

The Figma KPI cards remain unavailable until their exact metric definitions and source lineage are separately approved. The initial report, if approved, is an account-level program statement, not a statutory financial statement or audit-certified export.

## Consequences

- The financial-history page is labeled **سوابق ثبت‌شده در دفترکل بادبان** and explicitly states **ثبت داخلی؛ نه تأیید انتقال بانکی**.
- The reports page presents an account-level **صورت‌وضعیت دفترکل برنامه**, with currency and ledger-layer separation. Unapproved KPI cards remain unavailable.
- The two read endpoints reuse the existing program-scoped role grant and internal posted-journal facts; no parallel ledger or bank integration is created.
- Implementation remains subject to exact-head CI, code review, and the normal Stage/QA/Release/Production gates. This decision itself grants no merge or deployment authority.

## Approval record

The owner explicitly accepted this decision on 2026-11-06. This authorizes only the read-only code scope described above. It does not authorize merge, Stage, QA, Release, Production deployment, or real-money behavior.
