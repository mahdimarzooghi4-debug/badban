# Sprint 23 — Technical Code Review Record

- **Status:** Code Review Complete (technical review; not independent human release approval)
- **Date:** 2026-10-09
- **Scope:** BL-032 Portfolio Risk Numeric Integrity
- **PR:** #26, Draft/Open
- **Reviewed code HEAD:** `bd9b081875018580f92d90a027765f3bd18051e9`
- **Code CI:** #409 — SUCCESS
- **Base:** Sprint 22 / PR #25

## Files Reviewed

- `src/badban/application/risk.py` — risk decimal parsing, bounds, high-precision arithmetic.
- `tests/test_sprint23_risk_decimal_integrity.py` — fixed-point/scientific notation regression.
- Decision 0050, Sprint 23 contract, and 2026-10-09 Backlog Readiness inventory.

## Confirmed Invariants

1. Positive exponent integer precision (`1E+20`) now fails NUMERIC(38,18)
   instead of bypassing validation.
2. Policy-sourced decimal values are validated with the same exact storage
   limits before they affect any PortfolioRiskSnapshot.
3. Exact decimal addition for reserved/active exposure and evaluated
   near-threshold ratios uses scoped 80-digit local precision. That exceeds
   the 76 digits needed for the product/comparison of two NUMERIC(38,18)
   operands, without changing any policy-defined thresholds.
4. Derived exposure exceeding 20 integer digits fails before snapshot
   creation, instead of silently rounding/truncating.
5. NaN, Infinity, negative values, excessive decimal scale and unrepresentable
   values continue to fail closed.
6. Existing GREEN/AMBER/RED classification, caller authorization, snapshot,
   audit/outbox, provider, Journal, and HTTP contracts are unchanged.

## Finding Closed During CI

CI #408 failed only at `ruff format --check` for an assertion layout in the
new regression test. Commit `bd9b081875018580f92d90a027765f3bd18051e9`
fixed that formatting issue without feature additions. Exact-head CI #409
then completed successfully.

## Tests and Evidence

Tests cover scientific notation overflow, policy limit/ratio precision,
fractional scale overflow, valid boundary scientific notation, preserved
38-digit fractional increments, summed exposure overflow, and near-1.0
utilization comparison.

CI #409 included Secret Scan, Format, Lint, Type Check, Migrations, Migration
Drift, Tests, Dependency Audit and Container Build. This is Code/CI evidence,
not Stage, end-to-end financial QA, or independent human security approval.

## Deliberate Non-Goals and Remaining Risk

This review does not approve a reserve eligibility formula, zero-reserve
requirement interpretation, concentration/stress policy, BL-020 allocation,
portfolio risk snapshot freshness contract, or live data source. The existing
risk endpoint's explicit inputs are not newly authenticated against an
external reserve provider by this Sprint. Those remain distinct governance
gates; none are made safe by numeric hardening alone.

No Merge, Stage, QA, Release or Production has been executed or approved.

## Gate Result

`Technical Code Review = COMPLETE`.
`Merge / Stage / Production = NOT AUTHORIZED`.
