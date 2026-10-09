from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

import pytest

from badban.application.delinquency import (
    DelinquencyDefinition,
    DelinquencyDefinitionRegistry,
    DelinquencyEvaluationError,
    DelinquencyEvidence,
    parse_delinquency_definition,
)
from badban.application.lender_adapter import NormalizedLenderEvent


class FixedResultEvaluator:
    definition_type = "TEST_EXPLICIT"
    definition_version = "1"
    evaluator_version = "TEST_EVALUATOR_V1"

    def __init__(self, result: str) -> None:
        self._result = result
        self.last_definition: DelinquencyDefinition | None = None
        self.last_evidence: DelinquencyEvidence | None = None
        self.last_effective_at: datetime | None = None

    def evaluate(
        self,
        *,
        definition: DelinquencyDefinition,
        evidence: DelinquencyEvidence,
        effective_at: datetime,
    ) -> Any:
        self.last_definition = definition
        self.last_evidence = evidence
        self.last_effective_at = effective_at
        return self._result


def _raw_definition() -> dict[str, Any]:
    return {
        "definition_type": "TEST_EXPLICIT",
        "definition_version": "1",
        "payload": {
            "fixture_reference": "test-only-no-production-rule",
        },
    }


def _event() -> NormalizedLenderEvent:
    now = datetime.now(UTC)
    return NormalizedLenderEvent(
        provider_id=uuid4(),
        external_event_id="evt-delinquency-1",
        event_type="LOAN_DELINQUENT",
        schema_version=1,
        external_loan_id="loan-delinquency-1",
        event_time=now,
        received_at=now,
        original_principal="100",
        disbursed_principal=None,
        outstanding_principal="90",
        currency="IRR",
        repayment_reference=None,
        delinquency_state="PROVIDER_REPORTED_STATE",
        evidence_references=["evidence:test:delinquency"],
        payload_hash="a" * 64,
        provider_contract_version="provider-contract-v1",
        adapter_mapping_version="adapter-mapping-v1",
        inbound_normalization_version="inbound-v1",
        provider_event_sequence=4,
        guarantee_case_id=None,
        correlation_id=uuid4(),
    )


def test_parse_delinquency_definition_requires_explicit_versioned_envelope() -> None:
    parsed = parse_delinquency_definition(_raw_definition())

    assert parsed.definition_type == "TEST_EXPLICIT"
    assert parsed.definition_version == "1"
    assert parsed.payload == {"fixture_reference": "test-only-no-production-rule"}

    for invalid in (
        {},
        {"definition_version": "1", "payload": {}},
        {"definition_type": "TEST_EXPLICIT", "payload": {}},
        {
            "definition_type": "TEST_EXPLICIT",
            "definition_version": "1",
        },
        {
            "definition_type": "TEST_EXPLICIT",
            "definition_version": "1",
            "payload": [],
        },
        {
            "definition_type": "TEST_EXPLICIT",
            "definition_version": "1",
            "payload": {},
            "implicit_default": True,
        },
    ):
        with pytest.raises(DelinquencyEvaluationError) as exc:
            parse_delinquency_definition(cast(dict[str, Any], invalid))
        assert exc.value.code in {
            "DELINQUENCY_DEFINITION_MISSING",
            "DELINQUENCY_DEFINITION_INVALID",
        }


def test_registry_rejects_duplicate_and_unknown_definition_without_fallback() -> None:
    registry = DelinquencyDefinitionRegistry()
    evaluator = FixedResultEvaluator("NOT_SATISFIED")
    registry.register(evaluator)

    with pytest.raises(DelinquencyEvaluationError) as duplicate:
        registry.register(FixedResultEvaluator("SATISFIED"))
    assert duplicate.value.code == "DELINQUENCY_DEFINITION_INVALID"

    with pytest.raises(DelinquencyEvaluationError) as unknown:
        registry.resolve(
            definition_type="UNREGISTERED",
            definition_version="99",
        )
    assert unknown.value.code == "DELINQUENCY_DEFINITION_UNSUPPORTED"


@pytest.mark.parametrize(
    "result",
    [
        "SATISFIED",
        "NOT_SATISFIED",
        "INSUFFICIENT_EVIDENCE",
    ],
)
def test_registry_preserves_exact_evaluation_vocabulary(result: str) -> None:
    registry = DelinquencyDefinitionRegistry()
    evaluator = FixedResultEvaluator(result)
    registry.register(evaluator)
    evidence = DelinquencyEvidence.from_lender_event(_event(), processed_status="APPLIED")
    effective_at = datetime.now(UTC)

    evaluated = registry.evaluate(
        raw_definition=_raw_definition(),
        evidence=evidence,
        effective_at=effective_at,
    )

    assert evaluated.result == result
    assert evaluated.evaluator_version == "TEST_EVALUATOR_V1"
    assert evaluated.definition_type == "TEST_EXPLICIT"
    assert evaluated.definition_version == "1"
    assert evaluator.last_definition is not None
    assert evaluator.last_definition.payload == {
        "fixture_reference": "test-only-no-production-rule"
    }
    assert evaluator.last_evidence == evidence
    assert evaluator.last_effective_at == effective_at


def test_registry_rejects_unsupported_evaluator_result() -> None:
    registry = DelinquencyDefinitionRegistry()
    registry.register(FixedResultEvaluator("IMPLICITLY_SAFE"))

    with pytest.raises(DelinquencyEvaluationError) as exc:
        registry.evaluate(
            raw_definition=_raw_definition(),
            evidence=DelinquencyEvidence.from_lender_event(_event(), processed_status="APPLIED"),
            effective_at=datetime.now(UTC),
        )

    assert exc.value.code == "DELINQUENCY_DEFINITION_INVALID"


def test_evidence_is_derived_only_from_normalized_lender_lineage() -> None:
    event = _event()
    evidence = DelinquencyEvidence.from_lender_event(event, processed_status="APPLIED")

    assert evidence.provider_id == event.provider_id
    assert evidence.external_event_id == event.external_event_id
    assert evidence.event_type == "LOAN_DELINQUENT"
    assert evidence.external_loan_id == event.external_loan_id
    assert evidence.event_time == event.event_time
    assert evidence.received_at == event.received_at
    assert evidence.delinquency_state == event.delinquency_state
    assert evidence.evidence_references == tuple(event.evidence_references)
    assert evidence.payload_hash == event.payload_hash
    assert evidence.provider_contract_version == event.provider_contract_version
    assert evidence.adapter_mapping_version == event.adapter_mapping_version
    assert evidence.inbound_normalization_version == event.inbound_normalization_version
    assert evidence.provider_event_sequence == event.provider_event_sequence
    assert evidence.processed_status == "APPLIED"


def test_registry_fails_closed_on_insufficient_or_invalid_evidence() -> None:
    registry = DelinquencyDefinitionRegistry()
    evaluator = FixedResultEvaluator("SATISFIED")
    registry.register(evaluator)
    valid = DelinquencyEvidence.from_lender_event(_event(), processed_status="APPLIED")
    invalid = DelinquencyEvidence(
        provider_id=valid.provider_id,
        external_event_id=valid.external_event_id,
        event_type=valid.event_type,
        external_loan_id=valid.external_loan_id,
        event_time=valid.event_time,
        received_at=valid.received_at,
        delinquency_state=valid.delinquency_state,
        evidence_references=valid.evidence_references,
        payload_hash="",
        provider_contract_version=valid.provider_contract_version,
        adapter_mapping_version=valid.adapter_mapping_version,
        inbound_normalization_version=valid.inbound_normalization_version,
        provider_event_sequence=valid.provider_event_sequence,
        processed_status=valid.processed_status,
    )

    with pytest.raises(DelinquencyEvaluationError) as exc:
        registry.evaluate(
            raw_definition=_raw_definition(),
            evidence=invalid,
            effective_at=datetime.now(UTC),
        )

    assert exc.value.code == "DELINQUENCY_EVIDENCE_INSUFFICIENT"
    assert evaluator.last_definition is None


@pytest.mark.parametrize("processed_status", ["STALE", "HISTORY_ONLY"])
def test_registry_rejects_non_applied_lender_history(processed_status: str) -> None:
    registry = DelinquencyDefinitionRegistry()
    evaluator = FixedResultEvaluator("SATISFIED")
    registry.register(evaluator)

    with pytest.raises(DelinquencyEvaluationError) as exc:
        registry.evaluate(
            raw_definition=_raw_definition(),
            evidence=DelinquencyEvidence.from_lender_event(
                _event(),
                processed_status=processed_status,
            ),
            effective_at=datetime.now(UTC),
        )

    assert exc.value.code == "DELINQUENCY_EVIDENCE_INSUFFICIENT"
    assert evaluator.last_definition is None


def test_registry_requires_applied_delinquency_event_not_other_lender_event() -> None:
    registry = DelinquencyDefinitionRegistry()
    evaluator = FixedResultEvaluator("SATISFIED")
    registry.register(evaluator)
    valid = DelinquencyEvidence.from_lender_event(
        _event(),
        processed_status="APPLIED",
    )
    invalid = DelinquencyEvidence(
        provider_id=valid.provider_id,
        external_event_id=valid.external_event_id,
        event_type="LOAN_APPROVED",
        external_loan_id=valid.external_loan_id,
        event_time=valid.event_time,
        received_at=valid.received_at,
        delinquency_state=None,
        evidence_references=valid.evidence_references,
        payload_hash=valid.payload_hash,
        provider_contract_version=valid.provider_contract_version,
        adapter_mapping_version=valid.adapter_mapping_version,
        inbound_normalization_version=valid.inbound_normalization_version,
        provider_event_sequence=valid.provider_event_sequence,
        processed_status="APPLIED",
    )

    with pytest.raises(DelinquencyEvaluationError) as exc:
        registry.evaluate(
            raw_definition=_raw_definition(),
            evidence=invalid,
            effective_at=datetime.now(UTC),
        )

    assert exc.value.code == "DELINQUENCY_EVIDENCE_INSUFFICIENT"
    assert evaluator.last_definition is None


def test_registry_rejects_invalid_processing_lineage_and_payload_hash() -> None:
    registry = DelinquencyDefinitionRegistry()
    evaluator = FixedResultEvaluator("SATISFIED")
    registry.register(evaluator)
    valid = DelinquencyEvidence.from_lender_event(
        _event(),
        processed_status="APPLIED",
    )

    invalid_hash = replace(valid, payload_hash="not-a-sha256")
    with pytest.raises(DelinquencyEvaluationError) as hash_exc:
        registry.evaluate(
            raw_definition=_raw_definition(),
            evidence=invalid_hash,
            effective_at=datetime.now(UTC),
        )
    assert hash_exc.value.code == "DELINQUENCY_EVIDENCE_INSUFFICIENT"

    invalid_lineage = replace(valid, provider_contract_version="")
    with pytest.raises(DelinquencyEvaluationError) as lineage_exc:
        registry.evaluate(
            raw_definition=_raw_definition(),
            evidence=invalid_lineage,
            effective_at=datetime.now(UTC),
        )
    assert lineage_exc.value.code == "DELINQUENCY_EVIDENCE_INSUFFICIENT"


def test_registry_requires_timezone_aware_effective_timestamp() -> None:
    registry = DelinquencyDefinitionRegistry()
    registry.register(FixedResultEvaluator("NOT_SATISFIED"))

    with pytest.raises(DelinquencyEvaluationError) as exc:
        registry.evaluate(
            raw_definition=_raw_definition(),
            evidence=DelinquencyEvidence.from_lender_event(_event(), processed_status="APPLIED"),
            effective_at=datetime(2026, 10, 9, 12, 0, 0),
        )

    assert exc.value.code == "DELINQUENCY_DEFINITION_INVALID"
