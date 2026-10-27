# Technical Architecture — Three-Service Domain Boundaries

- **Status:** Technical design addendum; downstream implementation is not yet authorized by this document alone.
- **Business source:** `docs/business/03-original-proposal-product-alignment.md` (stacked change in PR #50).
- **Baseline:** Existing modular Python service and PostgreSQL persistence, as represented by the current technical foundation.
- **Purpose:** Specify the domain separation and reusable foundations required for all three Badban services without inventing unresolved business formulas or operational facts.

## 1. Architecture direction

Keep one Badban platform and participant financial case, with distinct service aggregates and lifecycle rules. Reuse identity, participant, policy/versioning, asset/valuation evidence, return allocation, ledger, audit, reconciliation, and notification primitives where applicable.

Do not model the three services as three labels over the GuaranteeCase aggregate. Guarantee exposure, monthly pension entitlements, and post-exit entitlements have different legal/operational events, balances, permissions, and closure conditions.

## 2. Service catalogue

Each service definition must have a stable type, version, lifecycle state, and a link to an approved policy version:

- `LOAN_GUARANTEE`: existing guarantee case, backing reservation, legal issuance, lender loan mirror, repayment, claim/recovery, and release flow.
- `MONTHLY_PENSION`: participant service enrollment plus period-specific entitlement and disbursement record.
- `POST_EXIT_SUPPORT`: exit-linked enrollment, eligibility decision, bounded support window (at most three years), period-specific entitlement, and completion/suspension record.

Product catalogue metadata may be configurable, but policy versions used by a decision or entitlement must be immutable snapshots. Changes apply prospectively according to approved policy; they must not rewrite issued guarantees or already decided periods.

## 3. Shared domain boundaries

### ParticipantFinancialCase

A read-oriented case groups the participant identity reference, funding/ownership references, asset position summaries, service enrollments, entitlement summaries, guarantee cases, and reconciled journal references. It is not the owner of any service lifecycle and must not merge distinct monetary balances.

### ServiceEnrollment

Represents a participant's enrollment/request for one service and captures service type, participant/program references, lifecycle state, submitted evidence references, decision result, and the exact policy version used. Each service gets its own enrollment and state.

### ReturnAllocation

Represents only eligible, realized, reconciled investment returns allocated under an approved policy to separately named destinations, including livelihood support, future financial support, reserves, capital growth, social reinvestment, or carry-forward as allowed. It references authoritative source observations and journal postings. Forecast values cannot fund payable entitlements.

### Entitlement

Represents one participant amount for one service and one policy-defined period, with source allocation references, amount/currency, decision snapshot, approval evidence, payment instruction reference (if configured), payment result, reconciliation state, and audit lineage. The principal balance is never an entitlement source.

## 4. Service lifecycle contracts

### Monthly pension

The system must support a period-based lifecycle that can represent eligibility, calculation, review/approval where required, payable, payment-pending, paid, failed, suspended, and closed outcomes. It must calculate only from eligible realized return allocations and approved policy inputs. The exact amount formula, eligibility, period cut-off, rounding, and payment timing remain policy inputs; no defaults are asserted here.

Duplicate generation or payment callbacks must be idempotent. Failed or reversed disbursement evidence must remain visible and reconcilable; it must not silently mark an entitlement paid.

### Post-exit support

A support case is linked to a participant exit event but is separate from the participation episode's closure and from financial closure. The approved policy defines eligibility, start date, amount formula, cadence, and any pause/resume conditions. The configured total window cannot exceed three years. Each period receives its own entitlement and immutable decision snapshot. Financial or guarantee obligations that survive program exit remain independently visible.

### Loan guarantee

Preserve the existing guarantee-specific invariants: external lender remains lender of record; legal issuance requires an authorized issuer and evidence; activation requires authoritative lender disbursement; the existing one-to-one pilot principal/guarantee constraint remains in force wherever the accepted pilot policy applies. Do not route monthly or post-exit entitlements through guarantee state transitions.

## 5. Integration boundaries

- **Investment/value engine:** supplies versioned observations and eligible realized return evidence; it does not make a participant entitlement payable by itself.
- **External sources:** lender, payment, pricing, identity, custody, and other integrations use configurable adapters and evidence registries. Unconfigured adapters return an explicit unavailable/not-configured state.
- **Journal and reconciliation:** every approved allocation and financial transition references balanced posting templates and source evidence under existing accounting controls.
- **Applicant surface:** exposes only the participant's own case, service decisions, entitlements, and verified payment/guarantee history.
- **Admin surface:** scopes commands by role and service, supports policy and maker-checker controls where configured, and records decision/audit evidence.
- **Lender surface:** exposes lender-scoped guarantee requests and guarantee/loan/repayment reconciliation only; no pension or post-exit entitlement data.

## 6. Required technical backlog capabilities

The ordered backlog should add or expand:

1. service catalogue and service-specific policy schema/version capture;
2. monthly pension enrollment, entitlement calculation, approval, disbursement evidence, idempotency, and reconciliation;
3. post-exit support eligibility and bounded period lifecycle, with independent case and entitlement history;
4. shared participant financial-case read model across the three service aggregates;
5. role/tenant scopes for applicant, admin roles, and lender organizations;
6. adapter readiness and explicit unavailable status for external price/payment/lender sources;
7. cross-service audit, reporting, and financial reconciliation without balance conflation.

Acceptance criteria must use policy-provided values and synthetic fixtures for tests; they must not encode unapproved thresholds, amounts, legal actors, payment rails, or live provider behavior.

## 7. Readiness boundary

The current implementation is guarantee-heavy and contains shared foundations; it is not complete for all three services. This architecture addendum records the required shape only. Product formulas and eligibility rules remain business/policy inputs. Code should begin only through an explicitly scoped sprint with approved acceptance criteria.
