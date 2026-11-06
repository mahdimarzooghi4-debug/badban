# Sprint 70 — Institution Financial History and Reporting Empty States

**Status:** Draft implementation, stacked on Sprint 69 / Draft PR #80; no merge or deployment.
**Figma:** Badban file ubJTK7Vt3lwSEeVdjyn59n, Institution / 07 246:332 (financial history) and Institution / 08 246:512 (reports).

## Approved bounded scope

- Make only the existing institution sidebar entries **سوابق مالی** and **گزارش‌ها** navigable. Keep the existing program/participant workspace under **داشبورد**. Do not activate the still-deferred **افراد** and **تأمین سرمایه** navigation entries.
- Recreate the two Figma page structures in responsive Persian RTL using editable React content and original local Figma SVG icons.
- Both pages explicitly communicate that their authoritative financial/aggregate data sources are not connected. They are product UI pages, not live finance workspaces.
- Financial history uses an empty state for cash funding/transaction history. It does not invent people, amounts, transaction identifiers, payment statuses, or request states.
- Reporting shows unavailable indicators and an empty chart region; it does not invent headcounts, balances, ownership aggregates, percentages, returns, or audit-ready reports.
- Show only the established scope and interpretation boundaries: program grants restrict visibility; sensitive identity details are not displayed; organizational principal and beneficiary rights are distinct; no guaranteed return is implied.

## Explicit non-goals

No backend endpoint, database, migration, finance ledger, projection, report calculation, transaction list, export, file download, payment, transfer, funding request, reconciliation, or authorization change. No API request is made by either empty-state page. The screens must never substitute zero or mock values for unavailable data.

## Validation and gates

Vitest server-rendered tests assert the empty states, no demo names/amounts/transactions, no form or mutation controls, and accessible status semantics. Python repository tests validate local Figma SVG dimensions and navigation wiring. Full exact-head CI and technical Code Review remain required. PR stays Draft/Open. Stage, QA, Release Approval and Production remain separate gates; no merge or deployment is included.
