# Sprint 71 — Supporting Institution Internal Financial History and Program Statement

- **Status:** Planning proposal only; waiting for explicit acceptance of Decision 0078.
- **Stack:** Draft PR #81 (Sprint 70) → this proposal.
- **Primary decision:** [0078 — Supporting Institution Internal Financial History and Program Statement](../decisions/0078-supporting-institution-internal-financial-history-and-program-statement.md).

## Source inventory

| Existing capability | What it can authoritatively provide | What it does not provide |
|---|---|---|
| `GET /api/v1/support-institution/programs` | Programs assigned through an active exact-program role grant | Global institution-wide access |
| `GET /api/v1/support-institution/programs/{program_id}/beneficiaries` | Program-scoped participant/episode references, participation and consent state | Financial history or organization-level totals |
| Existing beneficiary `financial-case` route | One exact participant episode's program-attributed assets, source-stamped valuations, guarantees and linked lender mirror facts | Program-wide journal history or an institution statement |
| `InternalPostedJournalSource` | Read-only, exact-program POSTED journal balances, account/owner/legal-entity/currency dimensions, evidence references and content hash | A public supporting-institution route, bank transactions or settlement confirmation |
| `GET /api/v1/finance/journals` | POSTED journals under finance-reconciliation/auditor legal-entity authorization | Access for the supporting-institution operator role |
| Asset positions and valuation observations | Quantity and separately sourced point-in-time valuation observations | Cash balance or confirmed settlement |
| Guarantee cases and external-loan mirrors | Guarantee exposure and lender-reported mirror state | Badban cash, bank proof or program capital total |

## Proposed implementation after acceptance

1. Add exact-program, read-only, audited financial-history and program-statement API routes.
2. Reuse persisted POSTED journal facts and the accepted internal source contract; fail closed for unavailable or mixed-scope evidence.
3. Keep currencies, account codes, legal entity, economic-owner class and ledger layer separate. Do not aggregate memo/external-mirror rows into cash.
4. Bind the two existing Figma pages to these APIs. Rename the history heading so it cannot be mistaken for bank transaction history.
5. Keep undefined KPI cards unavailable until their metric definitions and source lineage are explicitly approved.
6. Add endpoint-level authorization, isolation, pagination, multi-currency, mixed-scope, reversal, source-unavailable, and no-bank/no-mutation tests.

## Acceptance gates

- Decision 0078 must be explicitly accepted before code starts.
- Exact active program grant and active program/legal-entity lineage are mandatory on every read.
- Only POSTED evidence is eligible; absence is unavailable, not zero.
- No bank/payment/settlement provider is assumed or called.
- No money movement, posting, reversal, reconciliation mutation, eligibility or allocation behavior is added.
- No cross-program roll-up, participant-level balances in aggregate reports, FX conversion, or undefined KPI is introduced.
- Exact-head CI and technical Code Review remain required. PRs remain Draft/Open. No merge, Stage, QA, Release Approval, or Production deployment is included.
