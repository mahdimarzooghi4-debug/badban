from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest

from badban.application.reserve_policy import (
    ReserveEligibilityDefinitionRegistry,
    ReserveMetricsEvidence,
    ReservePolicyDefinition,
    ReservePolicyEvaluationError,
    ReserveRequirementDefinitionRegistry,
    ReserveRequirementEvidence,
    parse_reserve_policy_definition,
)
from badban.infrastructure.persistence.models import GuaranteeReserveMetricsSnapshot


class FixedRequirementEvaluator:
    definition_type = "TEST_REQUIREMENT"
    definition_version = "1"
    evaluator_version = "TEST_REQUIREMENT_V1"

    def __init__(self, result: Decimal) -> None:
        self.result = result
        self.last_definition: ReservePolicyDefinition | None = None
        self.last_evidence: ReserveRequirementEvidence | None = None

    def evaluate(
        self,
        *,
        definition: ReservePolicyDefinition,
        evidence: ReserveRequirementEvidence,
        effective_at: datetime,
    ) -> Decimal:
        assert effective_at.tzinfo is not None
        self.last_definition = definition
        self.last_evidence = evidence
        return self.result


class FixedEligibilityEvaluator:
    definition_type = "TEST_ELIGIBILITY"
    definition_version = "1"
    evaluator_version = "TEST_ELIGIBILITY_V1"

    def __init__(self, result: Decimal) -> None:
        self.result = result
        self.last_evidence: ReserveMetricsEvidence | None = None

    def evaluate(
        self,
        *,
        definition: ReservePolicyDefinition,
        evidence: ReserveMetricsEvidence,
        effective_at: datetime,
    ) -> Decimal:
        assert definition.payload == {"fixture_reference": "test-only"}
        assert effective_at.tzinfo is not None
        self.last_evidence = evidence
        return self.result


def _requirement_definition() -> dict[str, Any]:
    return {
        "definition_type": "TEST_REQUIREMENT",
        "definition_version": "1",
        "payload": {"fixture_reference": "test-only"},
    }


def _eligibility_definition() -> dict[str, Any]:
    return {
        "definition_type": "TEST_ELIGIBILITY",
        "definition_version": "1",
        "payload": {"fixture_reference": "test-only"},
    }


def _requirement_evidence() -> ReserveRequirementEvidence:
    return ReserveRequirementEvidence(
        input_values={
            "total_active_exposure": Decimal("100"),
            "portfolio_delinquency": Decimal("2"),
        },
        authoritative_input_references=(
            "portfolio-risk-source:test",
            "delinquency-metrics:test",
        ),
        evidence_version="TEST_REQUIREMENT_EVIDENCE_V1",
        evaluated_at=datetime.now(UTC),
    )


def _evidence() -> ReserveMetricsEvidence:
    snapshot_id = uuid4()
    return ReserveMetricsEvidence(
        snapshot_id=snapshot_id,
        reserve_metrics_reference=f"reserve-metrics:{snapshot_id}",
        legal_entity_id=uuid4(),
        currency="IRR",
        cash_control_balance=Decimal("100"),
        designated_balance=Decimal("80"),
        source_fingerprint="a" * 64,
        algorithm_code="GUARANTEE_RESERVE_METRICS",
        algorithm_version="GUARANTEE_RESERVE_METRICS_V1",
        evaluated_at=datetime.now(UTC),
    )


def test_definition_requires_explicit_versioned_envelope() -> None:
    parsed = parse_reserve_policy_definition(_requirement_definition())
    assert parsed.definition_type == "TEST_REQUIREMENT"
    assert parsed.definition_version == "1"
    assert parsed.payload == {"fixture_reference": "test-only"}

    invalid_definitions = [
        {},
        {"definition_type": "TEST_REQUIREMENT", "payload": {}},
        {"definition_version": "1", "payload": {}},
        {
            "definition_type": "TEST_REQUIREMENT",
            "definition_version": "1",
        },
        {
            "definition_type": "TEST_REQUIREMENT",
            "definition_version": "1",
            "payload": [],
        },
        {
            "definition_type": "TEST_REQUIREMENT",
            "definition_version": "1",
            "payload": {},
            "default_ratio": "0.1",
        },
    ]
    for raw in invalid_definitions:
        with pytest.raises(ReservePolicyEvaluationError) as exc:
            parse_reserve_policy_definition(raw)
        assert exc.value.code in {
            "RESERVE_POLICY_DEFINITION_MISSING",
            "RESERVE_POLICY_DEFINITION_INVALID",
        }


def test_requirement_registry_has_no_default_or_fallback_evaluator() -> None:
    registry = ReserveRequirementDefinitionRegistry()

    with pytest.raises(ReservePolicyEvaluationError) as exc:
        registry.evaluate(
            raw_definition=_requirement_definition(),
            evidence=_requirement_evidence(),
            effective_at=datetime.now(UTC),
        )

    assert exc.value.code == "RESERVE_POLICY_DEFINITION_UNSUPPORTED"


def test_requirement_registry_is_explicit_and_exact_decimal() -> None:
    registry = ReserveRequirementDefinitionRegistry()
    evaluator = FixedRequirementEvaluator(Decimal("42.125"))
    registry.register(evaluator)

    result = registry.evaluate(
        raw_definition=_requirement_definition(),
        evidence=_requirement_evidence(),
        effective_at=datetime.now(UTC),
    )

    assert result.required_reserve == Decimal("42.125")
    assert result.evaluator_version == "TEST_REQUIREMENT_V1"
    assert evaluator.last_definition is not None
    assert evaluator.last_evidence is not None
    assert evaluator.last_evidence.input_values["total_active_exposure"] == Decimal("100")
    assert evaluator.last_evidence.authoritative_input_references == (
        "portfolio-risk-source:test",
        "delinquency-metrics:test",
    )


def test_eligibility_registry_keeps_source_balances_separate() -> None:
    registry = ReserveEligibilityDefinitionRegistry()
    evaluator = FixedEligibilityEvaluator(Decimal("60"))
    registry.register(evaluator)
    evidence = _evidence()

    result = registry.evaluate(
        raw_definition=_eligibility_definition(),
        evidence=evidence,
        effective_at=datetime.now(UTC),
    )

    assert result.eligible_available_reserve == Decimal("60")
    assert evaluator.last_evidence == evidence
    assert evidence.cash_control_balance == Decimal("100")
    assert evidence.designated_balance == Decimal("80")


def test_duplicate_registration_and_unknown_definition_fail_closed() -> None:
    registry = ReserveEligibilityDefinitionRegistry()
    registry.register(FixedEligibilityEvaluator(Decimal("1")))

    with pytest.raises(ReservePolicyEvaluationError) as duplicate:
        registry.register(FixedEligibilityEvaluator(Decimal("2")))
    assert duplicate.value.code == "RESERVE_POLICY_DEFINITION_INVALID"

    with pytest.raises(ReservePolicyEvaluationError) as unknown:
        registry.evaluate(
            raw_definition={
                "definition_type": "UNKNOWN",
                "definition_version": "99",
                "payload": {},
            },
            evidence=_evidence(),
            effective_at=datetime.now(UTC),
        )
    assert unknown.value.code == "RESERVE_POLICY_DEFINITION_UNSUPPORTED"


@pytest.mark.parametrize(
    "bad_result",
    [
        Decimal("-1"),
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal("1.0000000000000000001"),
        Decimal("100000000000000000000"),
    ],
)
def test_invalid_evaluator_outputs_fail_closed(bad_result: Decimal) -> None:
    registry = ReserveRequirementDefinitionRegistry()
    registry.register(FixedRequirementEvaluator(bad_result))

    with pytest.raises(ReservePolicyEvaluationError) as exc:
        registry.evaluate(
            raw_definition=_requirement_definition(),
            evidence=_requirement_evidence(),
            effective_at=datetime.now(UTC),
        )

    assert exc.value.code == "RESERVE_POLICY_RESULT_INVALID"


def test_invalid_requirement_evidence_fails_before_evaluator_execution() -> None:
    registry = ReserveRequirementDefinitionRegistry()
    evaluator = FixedRequirementEvaluator(Decimal("10"))
    registry.register(evaluator)
    invalid = replace(
        _requirement_evidence(),
        input_values={"total_active_exposure": Decimal("-1")},
    )

    with pytest.raises(ReservePolicyEvaluationError) as exc:
        registry.evaluate(
            raw_definition=_requirement_definition(),
            evidence=invalid,
            effective_at=datetime.now(UTC),
        )

    assert exc.value.code == "RESERVE_POLICY_EVIDENCE_INVALID"
    assert evaluator.last_definition is None


def test_invalid_metrics_evidence_fails_before_eligibility_evaluator() -> None:
    registry = ReserveEligibilityDefinitionRegistry()
    evaluator = FixedEligibilityEvaluator(Decimal("10"))
    registry.register(evaluator)
    invalid = replace(_evidence(), cash_control_balance=Decimal("-1"))

    with pytest.raises(ReservePolicyEvaluationError) as exc:
        registry.evaluate(
            raw_definition=_eligibility_definition(),
            evidence=invalid,
            effective_at=datetime.now(UTC),
        )

    assert exc.value.code == "RESERVE_POLICY_EVIDENCE_INVALID"
    assert evaluator.last_evidence is None


def test_metrics_reference_must_bind_exact_snapshot() -> None:
    registry = ReserveEligibilityDefinitionRegistry()
    evaluator = FixedEligibilityEvaluator(Decimal("10"))
    registry.register(evaluator)
    invalid = replace(
        _evidence(),
        reserve_metrics_reference=f"reserve-metrics:{uuid4()}",
    )

    with pytest.raises(ReservePolicyEvaluationError) as exc:
        registry.evaluate(
            raw_definition=_eligibility_definition(),
            evidence=invalid,
            effective_at=datetime.now(UTC),
        )

    assert exc.value.code == "RESERVE_POLICY_EVIDENCE_INVALID"
    assert evaluator.last_evidence is None


def test_evidence_from_snapshot_preserves_exact_lineage() -> None:
    snapshot = GuaranteeReserveMetricsSnapshot(
        id=uuid4(),
        legal_entity_id=uuid4(),
        currency="IRR",
        cash_control_balance=Decimal("100"),
        designated_balance=Decimal("80"),
        source_journal_count=2,
        source_posting_count=2,
        source_journal_ids=[str(uuid4()), str(uuid4())],
        source_posting_ids=[str(uuid4()), str(uuid4())],
        source_fingerprint="b" * 64,
        algorithm_code="GUARANTEE_RESERVE_METRICS",
        algorithm_version="GUARANTEE_RESERVE_METRICS_V1",
        actor_type="STAFF",
        actor_id=uuid4(),
        correlation_id=uuid4(),
        evaluated_at=datetime.now(UTC),
    )

    evidence = ReserveMetricsEvidence.from_snapshot(snapshot)

    assert evidence.snapshot_id == snapshot.id
    assert evidence.reserve_metrics_reference == f"reserve-metrics:{snapshot.id}"
    assert evidence.legal_entity_id == snapshot.legal_entity_id
    assert evidence.currency == snapshot.currency
    assert evidence.cash_control_balance == Decimal("100")
    assert evidence.designated_balance == Decimal("80")
    assert evidence.source_fingerprint == snapshot.source_fingerprint
    assert evidence.algorithm_version == snapshot.algorithm_version


def test_timezone_aware_effective_time_is_required() -> None:
    registry = ReserveRequirementDefinitionRegistry()
    registry.register(FixedRequirementEvaluator(Decimal("10")))

    with pytest.raises(ReservePolicyEvaluationError) as exc:
        registry.evaluate(
            raw_definition=_requirement_definition(),
            evidence=_requirement_evidence(),
            effective_at=datetime(2026, 10, 9, 12, 0, 0),
        )

    assert exc.value.code == "RESERVE_POLICY_EVIDENCE_INVALID"
