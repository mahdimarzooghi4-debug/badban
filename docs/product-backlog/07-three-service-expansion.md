# Product Backlog Addendum — Monthly and Post-exit Services

- **Status:** Ordered backlog extension derived from the accepted Badban proposal alignment in PR #50 and technical boundaries in PR #51.
- **Scope:** Add service-specific requirements while retaining existing BL-038–BL-040 as shared financial foundations.
- **Ordering:** Product/policy contracts precede service lifecycle implementation; participant and admin read models follow authoritative lifecycle behavior.

## Existing backlog interpretation

- **BL-038 Return Recognition and Allocation** supplies a shared source/allocation foundation. It does not itself grant a participant a monthly pension or make an amount payable.
- **BL-039 Future Financial Entitlement** supplies a generic entitlement/payable-balance foundation. It does not define the post-exit service window, monthly pension recurrence, eligibility, approval, or period history.
- **BL-040 Participant Exit and Financial Reconciliation** governs exit and financial closure. It does not itself deliver a support service after exit.

These items remain reusable dependencies; the new items below make the three business services explicit and independently traceable.

## BL-054 — Configurable Three-Service Catalogue and Policy Contract

**Priority:** P1  
**Type:** Domain / Policy Capability  
**Depends on:** BL-006, BL-011, BL-012, BL-038  
**Traceability:** Business alignment §1–§6; Technical 16 §§2–3

**Acceptance Criteria**

- the catalogue represents `LOAN_GUARANTEE`, `MONTHLY_PENSION`, and `POST_EXIT_SUPPORT` as distinct stable service types;
- each service is independently enabled/disabled by approved versioned policy;
- policy schema can express eligibility references, amount/calculation references, period/cadence, approval requirements, suspension/resumption, and evidence requirements without hardcoding unknown values;
- a decision/enrollment captures an immutable policy version;
- policy edits cannot rewrite prior decisions, paid entitlements, or issued guarantee terms;
- unknown, missing, or inactive policy values fail closed and produce an explainable outcome.

## BL-055 — Monthly Pension Enrollment and Period Entitlement Lifecycle

**Priority:** P1  
**Type:** Financial Capability  
**Depends on:** BL-038, BL-039, BL-030, BL-041, BL-044, BL-054

**Acceptance Criteria**

- an eligible participant may have a distinct monthly pension enrollment;
- each policy-defined period has at most one entitlement per participant/service/period;
- only eligible realized return allocations can support payable amounts; principal and forecast return are excluded;
- calculation inputs, source allocations, policy version, and decision outcome are captured as immutable evidence;
- calculation, approval, payment instruction, payment result, reversal/failure, and reconciliation are distinct states/events;
- duplicate requests/events cannot create or pay the same entitlement twice;
- missing return evidence, policy, approval, or payment integration cannot produce a false payable/paid state.

The exact eligibility formula, payable amount formula, period cutoff, rounding, and disbursement timing are supplied through approved policy; this item defines no default values.

## BL-056 — Post-exit Support Enrollment and Bounded Period Entitlements

**Priority:** P1  
**Type:** Financial Capability  
**Depends on:** BL-013, BL-038, BL-039, BL-040, BL-030, BL-041, BL-044, BL-054

**Acceptance Criteria**

- the service is linked to a program exit event but has a distinct enrollment and lifecycle;
- policy can determine eligibility, start point, amount, cadence, pause/resume, and review inputs;
- approved support window is configurable but cannot exceed three years;
- each policy-defined period has one independently traceable entitlement and source-return allocation;
- participant exit does not erase active guarantee/financial obligations or imply financial closure;
- completion, early closure, suspension, failed payment, and reconciliation outcomes remain auditable;
- absent approved policy/evidence, the system cannot infer eligibility or create payable entitlement.

## BL-057 — Applicant Multi-service Financial Case Read Model

**Priority:** P2  
**Type:** Read Model / Applicant Capability  
**Depends on:** BL-016, BL-025, BL-039, BL-040, BL-054, BL-055, BL-056

**Acceptance Criteria**

- participant can see the three services, their own enrollments, requests, decisions, period entitlements, and verified payment/guarantee evidence;
- balances for principal, guarantee exposure, realized returns, allocated support, and paid amounts are shown separately;
- unavailable external sources and unconfigured payment/lender integrations are explicit;
- records are self-scoped; other participants' data and internal risk material are not exposed.

## BL-058 — Role-based Admin Service Operations

**Priority:** P2  
**Type:** Operations / Admin Capability  
**Depends on:** BL-044, BL-045, BL-046, BL-054, BL-055, BL-056

**Acceptance Criteria**

- admin capabilities are permissioned by role and service scope;
- authorized staff can review enrollments and period calculations without direct ledger editing;
- policy changes and high-impact decisions are versioned, audited, and maker-checker protected where required;
- finance, investment/value-engine, participant-case, oversight, and guarantee operations can be granted independently;
- audit/read models distinguish source evidence, calculated outcome, human action, payment instruction, and reconciliation result.

## BL-059 — Lender Portal Scope for Guarantee Operations

**Priority:** P2  
**Type:** Partner Operations Capability  
**Depends on:** BL-025, BL-026, BL-027, BL-042, BL-053, BL-054

**Acceptance Criteria**

- lender users are scoped to their authorized organization and guarantee/loan records;
- lender-facing actions cover guarantee request exchange, disbursement evidence, repayment/status exchange, and reconciliation;
- portal behavior preserves the lender-of-record and disbursement boundary;
- pension and post-exit entitlement data are not exposed to lender users.

## BL-060 — Universal Individual and Supporting Institution Access

**Priority:** P1  
**Type:** Identity / Participant and Partner Operations Capability  
**Depends on:** BL-006, BL-007, BL-009, BL-044, BL-054

**Acceptance Criteria**

- every authenticated individual can resolve a self-scoped Badban profile from a verified national ID, whether or not a supporting institution introduced them;
- profile creation does not imply program enrollment, capital assignment, service eligibility, or payment entitlement;
- supporting institutions can access only beneficiaries and financial records within their explicitly authorized program scope;
- ordinary individual capital and institution-assigned social capital remain distinguishable by ownership and funding source;
- identity data and financial details are not exposed across individual or institution boundaries.

## Delivery sequence

1. BL-054 policy/catalogue contract and a configurable service-type foundation.
2. BL-055 monthly pension lifecycle and BL-056 post-exit lifecycle on shared return/entitlement/ledger foundations.
3. BL-057 applicant case summary and BL-058 role-based admin operations.
4. BL-059 lender operations, retaining the existing guarantee path.
5. BL-060 universal individual access and supporting institution workspaces.
6. Cross-service reconciliation, reliability, security, and release readiness using existing platform controls.

No item permits production activation, real disbursement, or external source use without its accepted policy, contract, verified evidence, and operational approvals.
