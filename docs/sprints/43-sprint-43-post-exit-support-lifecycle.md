# Sprint 43 — Post-Exit Support Lifecycle

- **Status:** Implementation slice, stacked after Sprint 42.
- **Backlog:** BL-056.
- **Code authorization:** Decision 0061.
- **Financial source:** posted RETURN_ALLOCATION@1 credits to 2020.FUTURE_FINANCIAL_ENTITLEMENT.

## Sprint Goal

Represent policy-bound transitional support after a participant's documented exit, with separately audited case and period entitlement records, while preserving principal and preventing reuse of realized return allocations.

## In Scope

- Persist an exit-linked support case with evidence, policy/eligibility references, start date, configured duration, status, and distinct maker/checker activation.
- Require an active/effective POST_EXIT_SUPPORT catalogue version and enforce its configured 1–36 month maximum.
- Persist period entitlements with caller-defined period references and a sequence ordinal; don't invent calendar cadence.
- Reserve funds only from posted future-financial return-allocation lines for the same participant and currency.
- Enforce one entitlement per case and period sequence, one participant exit-event reference per case, and source allocation ceilings.
- Require a separate authorized checker to approve a fully funded entitlement.
- Add migration, admin APIs, audit evidence, and documentation.

## Out of Scope

- Eligibility/amount formulas, start-date rules, rounding, cadence, and any pause/resume policy beyond status controls; require policy inputs.
- Inference from a closed participation episode as proof of an exit event.
- Applicant self-service, payment instruction, settlement, or paid state.
- External providers, Stage, release, production, and merge.

## Acceptance Criteria

1. A support case references a verified exit-event evidence and a matching active/effective catalogue version.
2. Duration is positive and no more than the configured maximum and 36 months.
3. Period ordinals are 1 through the case duration; duplicate ordinals are rejected.
4. A draft period requires posted RETURN_ALLOCATION@1 credits to 2020.FUTURE_FINANCIAL_ENTITLEMENT for its participant and currency.
5. Fund allocation is atomic, source lines are locked, and total allocations never exceed the posted credit.
6. Case activation and entitlement approval require distinct authorized makers/checkers and produce audit events.
7. No endpoint represents a transfer or paid state.
8. Upgrade/downgrade migrations preserve existing financial records.

## Gates

- Exact-head CI and technical review are required.
- Sprint 43 remains Draft/unmerged. No Stage or release is authorized.
