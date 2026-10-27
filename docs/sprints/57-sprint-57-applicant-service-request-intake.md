# Sprint 57 — Applicant Service Request Intake

## Goal

Allow an ordinary individual to send an initial request for one of Badban's three services and see its receipt, without implying eligibility or creating a financial state.

## Deliverables

- Add an idempotent applicant endpoint for LOAN_GUARANTEE, MONTHLY_PENSION, and POST_EXIT_SUPPORT.
- Resolve or create the applicant profile from the verified OIDC claim; never accept a caller-supplied participant ID.
- Add a self-scoped request history endpoint.
- Add a service-scoped administrative queue using the existing service-role matrix.
- Expose the queue capability in the role-derived admin workspace.
- Persist, audit, and constrain request intake with a migration.

## Boundaries

- The request state is RECEIVED only; adjudication and eligibility are separate workflows.
- Submission does not enroll the individual in a program or create a guarantee, entitlement, payment, or obligation.
- No criteria, amounts, required evidence, contact workflow, or outcome statuses are assumed.
- No merge, Stage, QA release gate, Release, or Production operation is authorized.
