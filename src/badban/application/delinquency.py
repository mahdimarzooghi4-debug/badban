from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Protocol
from uuid import UUID

from badban.application.lender_adapter import NormalizedLenderEvent

DelinquencyEvaluationState = Literal[
    "SATISFIED",
    "NOT_SATISFIED",
    "INSUFFICIENT_EVIDENCE",
]

_ALLOWED_RESULTS = frozenset(
    {
        "SATISFIED",
        "NOT_SATISFIED",
        "INSUFFICIENT_EVIDENCE",
    }
)


class DelinquencyEvaluationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class DelinquencyDefinition:
    definition_type: str
    definition_version: str
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class DelinquencyEvidence:
    provider_id: UUID
    external_event_id: str
    event_type: str
    external_loan_id: str
    event_time: datetime
    received_at: datetime
    delinquency_state: str | None
    evidence_references: tuple[str, ...]
    payload_hash: str
    provider_contract_version: str
    adapter_mapping_version: str
    inbound_normalization_version: str
    provider_event_sequence: int | None
    processed_status: str

    @classmethod
    def from_lender_event(
        cls,
        event: NormalizedLenderEvent,
        *,
        processed_status: str,
    ) -> DelinquencyEvidence:
        return cls(
            provider_id=event.provider_id,
            external_event_id=event.external_event_id,
            event_type=event.event_type,
            external_loan_id=event.external_loan_id,
            event_time=event.event_time,
            received_at=event.received_at,
            delinquency_state=event.delinquency_state,
            evidence_references=tuple(event.evidence_references),
            payload_hash=event.payload_hash.lower(),
            provider_contract_version=event.provider_contract_version,
            adapter_mapping_version=event.adapter_mapping_version,
            inbound_normalization_version=event.inbound_normalization_version,
            provider_event_sequence=event.provider_event_sequence,
            processed_status=processed_status,
        )


@dataclass(frozen=True, slots=True)
class DelinquencyEvaluation:
    result: DelinquencyEvaluationState
    evaluator_version: str
    definition_type: str
    definition_version: str


class DelinquencyEvaluator(Protocol):
    definition_type: str
    definition_version: str
    evaluator_version: str

    def evaluate(
        self,
        *,
        definition: DelinquencyDefinition,
        evidence: DelinquencyEvidence,
        effective_at: datetime,
    ) -> DelinquencyEvaluationState: ...


def _required_text(value: object, *, field: str, missing_code: str, invalid_code: str) -> str:
    if value is None:
        raise DelinquencyEvaluationError(missing_code, f"{field} is required")
    if not isinstance(value, str) or not value.strip():
        raise DelinquencyEvaluationError(
            invalid_code,
            f"{field} must be a non-blank string",
        )
    return value.strip()


def parse_delinquency_definition(raw: dict[str, Any]) -> DelinquencyDefinition:
    if not isinstance(raw, dict) or not raw:
        raise DelinquencyEvaluationError(
            "DELINQUENCY_DEFINITION_MISSING",
            "Delinquency definition must be an explicit non-empty object",
        )

    definition_type = _required_text(
        raw.get("definition_type"),
        field="definition_type",
        missing_code="DELINQUENCY_DEFINITION_MISSING",
        invalid_code="DELINQUENCY_DEFINITION_INVALID",
    )
    definition_version = _required_text(
        raw.get("definition_version"),
        field="definition_version",
        missing_code="DELINQUENCY_DEFINITION_MISSING",
        invalid_code="DELINQUENCY_DEFINITION_INVALID",
    )
    if "payload" not in raw:
        raise DelinquencyEvaluationError(
            "DELINQUENCY_DEFINITION_MISSING",
            "payload is required",
        )
    payload = raw["payload"]
    if not isinstance(payload, dict):
        raise DelinquencyEvaluationError(
            "DELINQUENCY_DEFINITION_INVALID",
            "payload must be an object",
        )

    unexpected = sorted(set(raw) - {"definition_type", "definition_version", "payload"})
    if unexpected:
        raise DelinquencyEvaluationError(
            "DELINQUENCY_DEFINITION_INVALID",
            f"Unsupported delinquency definition fields: {','.join(unexpected)}",
        )

    return DelinquencyDefinition(
        definition_type=definition_type,
        definition_version=definition_version,
        payload=dict(payload),
    )


def _assert_aware_datetime(value: datetime, *, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise DelinquencyEvaluationError(
            "DELINQUENCY_DEFINITION_INVALID",
            f"{field} must be timezone-aware",
        )


def _validate_evidence(evidence: DelinquencyEvidence) -> None:
    _assert_aware_datetime(evidence.event_time, field="event_time")
    _assert_aware_datetime(evidence.received_at, field="received_at")
    if not evidence.external_event_id.strip() or not evidence.external_loan_id.strip():
        raise DelinquencyEvaluationError(
            "DELINQUENCY_EVIDENCE_INSUFFICIENT",
            "Authoritative lender event identity is required",
        )
    if evidence.event_type != "LOAN_DELINQUENT" or not (
        evidence.delinquency_state is not None and evidence.delinquency_state.strip()
    ):
        raise DelinquencyEvaluationError(
            "DELINQUENCY_EVIDENCE_INSUFFICIENT",
            "Applied lender-authoritative delinquency evidence is required",
        )
    if evidence.processed_status not in {"APPLIED", "CORRECTED"}:
        raise DelinquencyEvaluationError(
            "DELINQUENCY_EVIDENCE_INSUFFICIENT",
            "STALE or HISTORY_ONLY lender events cannot satisfy delinquency evaluation",
        )
    if len(evidence.payload_hash) != 64 or any(
        character not in "0123456789abcdefABCDEF" for character in evidence.payload_hash
    ):
        raise DelinquencyEvaluationError(
            "DELINQUENCY_EVIDENCE_INSUFFICIENT",
            "Authoritative lender payload hash must be a SHA-256 hex digest",
        )
    lineage_values = {
        "provider_contract_version": evidence.provider_contract_version,
        "adapter_mapping_version": evidence.adapter_mapping_version,
        "inbound_normalization_version": evidence.inbound_normalization_version,
    }
    if any(not value.strip() for value in lineage_values.values()):
        raise DelinquencyEvaluationError(
            "DELINQUENCY_EVIDENCE_INSUFFICIENT",
            "Lender processing lineage versions are required",
        )
    if any(not reference.strip() for reference in evidence.evidence_references):
        raise DelinquencyEvaluationError(
            "DELINQUENCY_EVIDENCE_INSUFFICIENT",
            "Evidence references must not contain blank values",
        )


class DelinquencyDefinitionRegistry:
    def __init__(self) -> None:
        self._evaluators: dict[tuple[str, str], DelinquencyEvaluator] = {}

    def register(self, evaluator: DelinquencyEvaluator) -> None:
        definition_type = _required_text(
            getattr(evaluator, "definition_type", None),
            field="definition_type",
            missing_code="DELINQUENCY_DEFINITION_INVALID",
            invalid_code="DELINQUENCY_DEFINITION_INVALID",
        )
        definition_version = _required_text(
            getattr(evaluator, "definition_version", None),
            field="definition_version",
            missing_code="DELINQUENCY_DEFINITION_INVALID",
            invalid_code="DELINQUENCY_DEFINITION_INVALID",
        )
        _required_text(
            getattr(evaluator, "evaluator_version", None),
            field="evaluator_version",
            missing_code="DELINQUENCY_DEFINITION_INVALID",
            invalid_code="DELINQUENCY_DEFINITION_INVALID",
        )
        key = (definition_type, definition_version)
        if key in self._evaluators:
            raise DelinquencyEvaluationError(
                "DELINQUENCY_DEFINITION_INVALID",
                "An evaluator is already registered for this definition type/version",
            )
        self._evaluators[key] = evaluator

    def resolve(
        self,
        *,
        definition_type: str,
        definition_version: str,
    ) -> DelinquencyEvaluator:
        key = (definition_type, definition_version)
        evaluator = self._evaluators.get(key)
        if evaluator is None:
            raise DelinquencyEvaluationError(
                "DELINQUENCY_DEFINITION_UNSUPPORTED",
                "No evaluator is registered for this definition type/version",
            )
        return evaluator

    def evaluate(
        self,
        *,
        raw_definition: dict[str, Any],
        evidence: DelinquencyEvidence,
        effective_at: datetime,
    ) -> DelinquencyEvaluation:
        _assert_aware_datetime(effective_at, field="effective_at")
        definition = parse_delinquency_definition(raw_definition)
        _validate_evidence(evidence)
        evaluator = self.resolve(
            definition_type=definition.definition_type,
            definition_version=definition.definition_version,
        )
        result = evaluator.evaluate(
            definition=definition,
            evidence=evidence,
            effective_at=effective_at,
        )
        if result not in _ALLOWED_RESULTS:
            raise DelinquencyEvaluationError(
                "DELINQUENCY_DEFINITION_INVALID",
                "Evaluator returned an unsupported delinquency result",
            )
        evaluator_version = _required_text(
            evaluator.evaluator_version,
            field="evaluator_version",
            missing_code="DELINQUENCY_DEFINITION_INVALID",
            invalid_code="DELINQUENCY_DEFINITION_INVALID",
        )
        return DelinquencyEvaluation(
            result=result,
            evaluator_version=evaluator_version,
            definition_type=definition.definition_type,
            definition_version=definition.definition_version,
        )
