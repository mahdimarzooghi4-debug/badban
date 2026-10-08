# Decision 0039 — Reconciliation Policy Governance and Fail-Closed Rule Binding

- **Status:** Accepted
- **Date:** 2026-10-08
- **Scope:** Technical clarification / BL-042 Reconciliation Engine Core / bounded external-lender pilot
- **Depends on:** Decisions 0015, 0016, 0018; Technical 04, 06, 10
- **Supersedes:** no prior decision

## Decision

Badban shall govern reconciliation comparison rules through the existing immutable/versioned PolicyVersion lifecycle using a dedicated policy type:

`RECONCILIATION_POLICY`.

A reconciliation run must bind to one exact governed Reconciliation Policy version referenced by the exact resolved Pilot Policy Pack. Reconciliation code must never select an implicit latest policy or silently fall back to a default rule set.

## Rule Ownership

A Reconciliation Policy may define rules per reconciliation type, including:

- permitted source freshness;
- comparison mode per field: exact, decimal-exact, or tolerance-based;
- tolerance only where explicitly supplied by the governed policy;
- materiality classification for mismatch reason codes;
- rule/mapping version metadata required for deterministic replay.

The policy stores configuration, not provider credentials or raw provider payloads.

## No Invented Values

This decision does **not** define any production:

- freshness duration;
- tolerance amount or percentage;
- numeric materiality threshold;
- provider-specific mapping;
- reconciliation cadence;
- blocking threshold.

Missing or invalid governed values fail closed. Code must not invent safe defaults.

## Hard Invariants

Accepted Technical invariants remain stronger than configurable policy.

In particular:

`Original External Loan Principal = Issued Badban Guarantee Amount`

Any contrary authoritative lender record is CRITICAL. Policy cannot downgrade this invariant.

Stale evidence is never MATCHED. Provider silence is never MATCHED.

## Lifecycle and Lineage

Reconciliation Policy versions use the existing PolicyVersion lifecycle:

`DRAFT → REVIEWED → APPROVED → ACTIVE → SUPERSEDED / RETIRED`.

A Pilot Policy Pack references exact PolicyVersion IDs. A run records the exact Reconciliation Policy ID/version and source cutoffs/evidence used.

Historical runs are never silently re-evaluated against a newer policy.

## BL-043 Boundary

Decision 0039 resolves rule-version ownership required for BL-042 only.

It does not authorize:

- reconciliation resolution workflow;
- maker-checker resolution;
- command-block activation/clearing;
- direct repair of financial/domain state.

Those remain BL-043 or later explicitly authorized work.

## Consequence

BL-042 Core may proceed without inventing reconciliation values, provided the implementation fails closed whenever its exact governed policy/rules are unavailable.
