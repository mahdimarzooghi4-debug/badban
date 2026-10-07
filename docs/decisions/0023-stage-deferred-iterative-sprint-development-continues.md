# Decision 0023 — Stage Deferred; Iterative Sprint Development Continues

- **Status:** Superseded
- **Superseded by:** Decision 0033 — Stage, QA, and Release Approval Gates Reactivated
- **Date:** 2026-10-05
- **Scope:** Delivery Process / Pre-Stage Development
- **Depends on:** Decision 0022

## Decision

Badban does not currently have an available Stage environment.

Stage execution is therefore **deferred**, and development may continue into the next Sprint rather than blocking all further implementation on an environment that does not yet exist.

This decision does not remove Stage from the parent delivery process and does not redefine Stage as optional.

## Delivery Rule

Until a Stage environment exists:

- completed Sprint code may proceed through Code Review and merge to `main`;
- the next approved Sprint may be planned and implemented;
- no work may claim Stage validation merely because CI/local integration tests pass;
- QA/Testing, Release Approval, Production, and real-money activation remain blocked by the missing Stage gate where the parent process requires it.

## Accumulated Stage Candidate

Merged, reviewed Sprint outputs become part of an **accumulated Stage candidate**.

When Stage becomes available, the Stage gate must validate the then-current explicitly selected release candidate, including all accumulated Sprint changes in scope.

A later Sprint does not erase an earlier Sprint's Stage obligations.

## Environment Boundary

CI/local/test environments remain non-Stage environments.

They may prove:

- automated correctness;
- migrations;
- integration behavior with local/test dependencies;
- security/static quality gates;
- container buildability.

They do not prove:

- production-like topology;
- production-equivalent identity/provider integration;
- Stage recovery/restore;
- Stage operational readiness;
- release readiness.

## Production Boundary

This decision grants no authorization for:

- QA/Testing gate completion;
- Release Approval;
- Production;
- real provider credentials;
- real-money activity.

## Consequence

Sprint Planning may proceed to Sprint 02.

Sprint 02 still requires its own explicit plan and Code authorization before implementation begins.
