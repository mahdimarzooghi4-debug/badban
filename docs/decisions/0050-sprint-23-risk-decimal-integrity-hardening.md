# Decision 0050 — Sprint 23 Portfolio Risk Decimal Integrity Hardening

- **Status:** Accepted (technical correctness scope only)
- **Date:** 2026-10-09
- **Scope:** Sprint 23 / BL-032 technical integrity maintenance
- **Base:** Sprint 22 Draft branch; no change to active production policy

## Finding

The existing risk decimal storage-bound validation under-counted integer digits for
positive-exponent values such as `1E+20`. Under the default 28-digit Decimal
context, adding two valid NUMERIC(38,18) exposures could also silently drop
fractional digits or mask representational overflow before validation.

## Authorized Remediation

- Validate exact NUMERIC(38,18) representability for both risk policy inputs
  and evaluated monetary inputs, including exponent and scale.
- Preserve enough precision for exact addition and risk-threshold comparisons
  of two representable 38-digit decimal inputs.
- Fail closed on unrepresentable derived committed exposure.
- Cover exponent, fractional scale, summed-overflow and near-boundary cases.
- Keep previous domain states, policy-defined thresholds, APIs and snapshot schema.

## Unchanged Business Boundaries

No risk/reserve percentages, portfolio limits, eligiblity policy, zero-required-
reserve semantics, concentration/stress defaults, or authoritative source
integration are authorized by this technical remediation. In particular it
does not activate reserve policy evaluators or authorize BL-020 reservation.

No Merge, Stage, QA/Release, Production, real-money or Direct Lending is
authorized here.
