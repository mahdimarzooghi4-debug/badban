from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from badban.application.risk import (
    RiskEvaluationError,
    RiskEvaluationInputs,
    RiskPolicyRules,
    calculate_portfolio_risk,
    parse_risk_policy_rules,
)


def _rules() -> RiskPolicyRules:
    # Values are test fixtures, not configured Production risk rules.
    return RiskPolicyRules(
        approved_portfolio_limit=Decimal("99999999999999999999.999999999999999999"),
        committed_exposure_mode="ACTIVE_PLUS_RESERVED",
        utilization_warning_ratio=Decimal("0.75"),
        utilization_stop_ratio=Decimal("1"),
        reserve_coverage_target_ratio=Decimal("1.25"),
        reserve_coverage_warning_ratio=Decimal("1"),
        reserve_coverage_hard_minimum_ratio=Decimal("0.75"),
        require_stress_result=False,
    )


def _inputs(active: str, reserved: str = "0") -> RiskEvaluationInputs:
    return RiskEvaluationInputs(
        total_active_exposure=Decimal(active),
        total_reserved_exposure=Decimal(reserved),
        reserve_requirement=Decimal("2"),
        reserve_available=Decimal("3"),
        reserve_metrics_reference="reserve:test:1",
        concentration_state="GREEN",
        concentration_metrics_reference="concentration:test:1",
        stress_state=None,
        stress_result_reference=None,
        authoritative_input_references=("source:test:1",),
    )


def _policy_payload() -> dict[str, object]:
    return {
        "approved_portfolio_limit": "100",
        "committed_exposure_mode": "ACTIVE_PLUS_RESERVED",
        "utilization_warning_ratio": "0.75",
        "utilization_stop_ratio": "1",
        "reserve_coverage_target_ratio": "1.25",
        "reserve_coverage_warning_ratio": "1",
        "reserve_coverage_hard_minimum_ratio": "0.75",
        "require_stress_result": False,
    }


@pytest.mark.parametrize("amount", ["1E+20", "1E+30", "999999999999999999999"])
def test_positive_exponent_or_integer_overflow_rejected_as_risk_input(amount: str) -> None:
    with pytest.raises(RiskEvaluationError, match="NUMERIC") as exc:
        calculate_portfolio_risk(rules=_rules(), inputs=_inputs(amount))
    assert exc.value.code == "RISK_INPUT_INVALID"


@pytest.mark.parametrize("amount", ["1E+20", "1E+30", "0.0000000000000000001"])
def test_out_of_storage_policy_parameters_fail_closed(amount: str) -> None:
    payload = _policy_payload()
    payload["approved_portfolio_limit"] = amount
    with pytest.raises(RiskEvaluationError, match="NUMERIC") as exc:
        parse_risk_policy_rules(payload)
    assert exc.value.code == "RISK_POLICY_INVALID"


def test_out_of_storage_policy_ratio_also_fails_closed() -> None:
    payload = _policy_payload()
    payload["reserve_coverage_target_ratio"] = "1E+20"
    with pytest.raises(RiskEvaluationError) as exc:
        parse_risk_policy_rules(payload)
    assert exc.value.code == "RISK_POLICY_INVALID"


def test_valid_scientific_notation_at_integer_boundary_is_accepted() -> None:
    payload = _policy_payload()
    payload["approved_portfolio_limit"] = "1E+19"
    rules = parse_risk_policy_rules(payload)
    assert rules.approved_portfolio_limit == Decimal("1E+19")
    result = calculate_portfolio_risk(
        rules=replace(_rules(), approved_portfolio_limit=Decimal("1E+19")),
        inputs=_inputs("1E+19"),
    )
    assert result.utilization_ratio == Decimal("1")
    assert result.gate_states["exposure"] == "RED"


def test_38_digit_exposure_sum_preserves_fractional_increment() -> None:
    result = calculate_portfolio_risk(
        rules=_rules(),
        inputs=_inputs(
            "99999999999999999999.000000000000000000",
            "0.000000000000000001",
        ),
    )
    assert result.committed_exposure == Decimal(
        "99999999999999999999.000000000000000001"
    )


def test_derived_exposure_overflow_rejected_without_rounding() -> None:
    with pytest.raises(RiskEvaluationError, match="NUMERIC") as exc:
        calculate_portfolio_risk(
            rules=_rules(),
            inputs=_inputs(
                "99999999999999999999.999999999999999999",
                "0.000000000000000001",
            ),
        )
    assert exc.value.code == "RISK_INPUT_INVALID"


def test_high_precision_ratio_does_not_round_hard_gate_to_safe_state() -> None:
    rules = replace(
        _rules(),
        approved_portfolio_limit=Decimal("99999999999999999999"),
    )
    result = calculate_portfolio_risk(
        rules=rules,
        inputs=_inputs("99999999999999999998.999999999999999999"),
    )
    assert result.utilization_ratio < Decimal("1")
    assert result.gate_states["exposure"] != "RED"
