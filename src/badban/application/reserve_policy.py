from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID

from badban.infrastructure.persistence.models import GuaranteeReserveMetricsSnapshot


class ReservePolicyEvaluationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class ReservePolicyDefinition:
    definition_type: str
    definition_version: str
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ReserveMetricsEvidence:
    snapshot_id: UUID
    reserve_metrics_reference: str
    legal_entity_id: UUID
    currency: str
    cash_control_balance: Decimal
    designated_balance: Decimal
    source_fingerprint: str
    algorithm_code: str
    algorithm_version: str
    evaluated_at: datetime

    @classmethod
    def from_snapshot(
        cls,
        snapshot: GuaranteeReserveMetricsSnapshot,
    ) -> ReserveMetricsEvidence:
        return cls(
            snapshot_id=snapshot.id,
            reserve_metrics_reference=f"reserve-metrics:{snapshot.id}",
            legal_entity_id=snapshot.legal_entity_id,
            currency=snapshot.currency,
            cash_control_balance=Decimal(snapshot.cash_control_balance),
            designated_balance=Decimal(snapshot.designated_balance),
            source_fingerprint=snapshot.source_fingerprint,
            algorithm_code=snapshot.algorithm_code,
            algorithm_version=snapshot.algorithm_version,
            evaluated_at=snapshot.evaluated_at,
        )


@dataclass(frozen=True, slots=True)
class ReserveRequirementEvaluation:
    required_reserve: Decimal
    evaluator_version: str
    definition_type: str
    definition_version: str


@dataclass(frozen=True, slots=True)
class ReserveEligibilityEvaluation:
    eligible_available_reserve: Decimal
    evaluator_version: str
    definition_type: str
    definition_version: str


class ReserveRequirementEvaluator(Protocol):
    definition_type: str
    definition_version: str
    evaluator_version: str

    def evaluate(
        self,
        *,
        definition: ReservePolicyDefinition,
        evidence: ReserveMetricsEvidence,
        effective_at: datetime,
    ) -> Decimal: ...


class ReserveEligibilityEvaluator(Protocol):
    definition_type: str
    definition_version: str
    evaluator_version: str

    def evaluate(
        self,
        *,
        definition: ReservePolicyDefinition,
        evidence: ReserveMetricsEvidence,
        effective_at: datetime,
    ) -> Decimal: ...


def _required_text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReservePolicyEvaluationError(
            "RESERVE_POLICY_DEFINITION_INVALID",
            f"{field} must be a non-blank string",
        )
    return value.strip()


def _assert_aware_datetime(value: datetime, *, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ReservePolicyEvaluationError(
            "RESERVE_POLICY_EVIDENCE_INVALID",
            f"{field} must be timezone-aware",
        )


def _exact_non_negative_decimal(value: object, *, field: str) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
        raise ReservePolicyEvaluationError(
            "RESERVE_POLICY_RESULT_INVALID",
            f"{field} must be a finite non-negative Decimal",
        )
    _sign, digits, exponent = value.as_tuple()
    if not isinstance(exponent, int):
        raise ReservePolicyEvaluationError(
            "RESERVE_POLICY_RESULT_INVALID",
            f"{field} must have a finite decimal exponent",
        )
    scale = max(0, -exponent)
    integer_digits = max(0, len(digits) - scale)
    if scale > 18 or integer_digits > 20:
        raise ReservePolicyEvaluationError(
            "RESERVE_POLICY_RESULT_INVALID",
            f"{field} exceeds NUMERIC(38,18) storage precision",
        )
    return value


def parse_reserve_policy_definition(raw: dict[str, Any]) -> ReservePolicyDefinition:
    if not isinstance(raw, dict) or not raw:
        raise ReservePolicyEvaluationError(
            "RESERVE_POLICY_DEFINITION_MISSING",
            "Reserve policy definition must be an explicit non-empty object",
        )
    required = {"definition_type", "definition_version", "payload"}
    missing = sorted(required - set(raw))
    if missing:
        raise ReservePolicyEvaluationError(
            "RESERVE_POLICY_DEFINITION_MISSING",
            f"Missing reserve policy definition fields: {','.join(missing)}",
        )
    unexpected = sorted(set(raw) - required)
    if unexpected:
        raise ReservePolicyEvaluationError(
            "RESERVE_POLICY_DEFINITION_INVALID",
            f"Unsupported reserve policy definition fields: {','.join(unexpected)}",
        )
    if not isinstance(raw["payload"], dict):
        raise ReservePolicyEvaluationError(
            "RESERVE_POLICY_DEFINITION_INVALID",
            "payload must be an object",
        )
    return ReservePolicyDefinition(
        definition_type=_required_text(raw["definition_type"], field="definition_type"),
        definition_version=_required_text(
            raw["definition_version"],
            field="definition_version",
        ),
        payload=dict(raw["payload"]),
    )


def validate_reserve_metrics_evidence(evidence: ReserveMetricsEvidence) -> None:
    if not evidence.currency.strip():
        raise ReservePolicyEvaluationError(
            "RESERVE_POLICY_EVIDENCE_INVALID",
            "currency must not be blank",
        )
    _assert_aware_datetime(evidence.evaluated_at, field="evaluated_at")
    _exact_non_negative_decimal(
        evidence.cash_control_balance,
        field="cash_control_balance",
    )
    _exact_non_negative_decimal(
        evidence.designated_balance,
        field="designated_balance",
    )
    if len(evidence.source_fingerprint) != 64 or any(
        character not in "0123456789abcdefABCDEF"
        for character in evidence.source_fingerprint
    ):
        raise ReservePolicyEvaluationError(
            "RESERVE_POLICY_EVIDENCE_INVALID",
            "source_fingerprint must be a SHA-256 hex digest",
        )
    _required_text(evidence.algorithm_code, field="algorithm_code")
    _required_text(evidence.algorithm_version, field="algorithm_version")
    expected_reference = f"reserve-metrics:{evidence.snapshot_id}"
    if evidence.reserve_metrics_reference != expected_reference:
        raise ReservePolicyEvaluationError(
            "RESERVE_POLICY_EVIDENCE_INVALID",
            "reserve_metrics_reference must bind to the exact snapshot",
        )


class _EvaluatorRegistry:
    def __init__(self) -> None:
        self._evaluators: dict[tuple[str, str], Any] = {}

    def register(self, evaluator: Any) -> None:
        definition_type = _required_text(
            getattr(evaluator, "definition_type", None),
            field="definition_type",
        )
        definition_version = _required_text(
            getattr(evaluator, "definition_version", None),
            field="definition_version",
        )
        _required_text(
            getattr(evaluator, "evaluator_version", None),
            field="evaluator_version",
        )
        key = (definition_type, definition_version)
        if key in self._evaluators:
            raise ReservePolicyEvaluationError(
                "RESERVE_POLICY_DEFINITION_INVALID",
                "An evaluator is already registered for this definition type/version",
            )
        self._evaluators[key] = evaluator

    def resolve(self, definition: ReservePolicyDefinition) -> Any:
        evaluator = self._evaluators.get(
            (definition.definition_type, definition.definition_version)
        )
        if evaluator is None:
            raise ReservePolicyEvaluationError(
                "RESERVE_POLICY_DEFINITION_UNSUPPORTED",
                "No evaluator is registered for this definition type/version",
            )
        return evaluator


class ReserveRequirementDefinitionRegistry(_EvaluatorRegistry):
    def evaluate(
        self,
        *,
        raw_definition: dict[str, Any],
        evidence: ReserveMetricsEvidence,
        effective_at: datetime,
    ) -> ReserveRequirementEvaluation:
        _assert_aware_datetime(effective_at, field="effective_at")
        definition = parse_reserve_policy_definition(raw_definition)
        validate_reserve_metrics_evidence(evidence)
        evaluator: ReserveRequirementEvaluator = self.resolve(definition)
        required_reserve = _exact_non_negative_decimal(
            evaluator.evaluate(
                definition=definition,
                evidence=evidence,
                effective_at=effective_at,
            ),
            field="required_reserve",
        )
        return ReserveRequirementEvaluation(
            required_reserve=required_reserve,
            evaluator_version=_required_text(
                evaluator.evaluator_version,
                field="evaluator_version",
            ),
            definition_type=definition.definition_type,
            definition_version=definition.definition_version,
        )


class ReserveEligibilityDefinitionRegistry(_EvaluatorRegistry):
    def evaluate(
        self,
        *,
        raw_definition: dict[str, Any],
        evidence: ReserveMetricsEvidence,
        effective_at: datetime,
    ) -> ReserveEligibilityEvaluation:
        _assert_aware_datetime(effective_at, field="effective_at")
        definition = parse_reserve_policy_definition(raw_definition)
        validate_reserve_metrics_evidence(evidence)
        evaluator: ReserveEligibilityEvaluator = self.resolve(definition)
        eligible_available_reserve = _exact_non_negative_decimal(
            evaluator.evaluate(
                definition=definition,
                evidence=evidence,
                effective_at=effective_at,
            ),
            field="eligible_available_reserve",
        )
        return ReserveEligibilityEvaluation(
            eligible_available_reserve=eligible_available_reserve,
            evaluator_version=_required_text(
                evaluator.evaluator_version,
                field="evaluator_version",
            ),
            definition_type=definition.definition_type,
            definition_version=definition.definition_version,
        )
