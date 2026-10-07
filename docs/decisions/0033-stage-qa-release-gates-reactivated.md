# Decision 0033 — Stage, QA, and Release Approval Gates Reactivated

- **Status:** Accepted
- **Date:** 2026-10-07
- **Scope:** Delivery Process / Stage Re-entry
- **Depends on:** Decision 0023; Sprint 08 / BL-030 merged to `main`; CI #218 green
- **Supersedes:** Decision 0023 to the extent that it defers Stage and blocks QA/Testing and Release Approval

## Decision

Stage is no longer deferred.

Badban returns to the canonical parent delivery process:

```
Business
→ Technical
→ Scrum/Product Backlog
→ Sprint
→ Code
→ Code Review
→ Stage
→ QA/Testing
→ Release Approval
→ Production
→ Monitoring
→ Improvement
```

The accumulated reviewed and merged implementation may now proceed into Stage, subject to an explicitly selected release candidate and real Stage evidence.

## Stage Gate

Stage may now be established, configured, and executed for an explicitly identified candidate from `main`.

Stage acceptance must be evidence-based. CI/local/test success is necessary but does not by itself constitute Stage acceptance.

A Stage pass requires the Stage environment and the selected candidate to demonstrate the applicable production-like integration, migration, security, observability, recovery, and operational checks defined by the accepted Technical and Sprint contracts.

If Stage fails, progression stops. The exact failure must be corrected, CI must return green, and the affected Stage checks must be rerun.

## QA/Testing Gate

QA/Testing is authorized only after Stage acceptance for the same selected release candidate.

QA/Testing must validate the applicable functional, integration, negative-path, authorization, financial-control, concurrency, and regression requirements.

A failed QA/Testing gate blocks Release Approval until corrected and revalidated.

## Release Approval Gate

Release Approval is authorized only after both Stage and QA/Testing are accepted for the selected release candidate.

Release Approval is a separate explicit gate. Stage or QA success does not itself approve a Production deployment.

## Production Boundary

This decision does **not** authorize Production deployment, real provider credentials, real-money activity, or any other Production activation.

Production still requires its own explicit approval after Release Approval.

## Sprint and Backlog Boundary

This decision changes the delivery-gate status only.

It does not automatically authorize new backlog implementation. In particular:

- BL-032 still requires its own Sprint/Code authorization before implementation;
- BL-020 remains blocked until authoritative BL-032 portfolio-risk PASS capability exists;
- no implicit GREEN, synthetic PASS, hard-coded safe default, or missing-risk-as-PASS behavior is authorized;
- existing business, legal, accounting, provider, and financial-control boundaries remain unchanged.

## Historical Decision References

Decision 0023 remains part of the immutable decision history but is superseded by this decision with respect to Stage deferral.

Any later historical Sprint/decision text that says Stage is deferred because Decision 0023 is in force is also superseded to that limited extent. Those historical records remain accurate descriptions of the gate at the time they were accepted.

## Consequence

Badban may now progress from reviewed/merged code into Stage, then QA/Testing, then Release Approval, while preserving explicit evidence and stop-gates at every step.

Production remains blocked until explicit Production authorization.
