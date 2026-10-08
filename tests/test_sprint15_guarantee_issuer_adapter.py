from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from badban.application.guarantee_issuer_adapter import (
    CANONICAL_GUARANTEE_ISSUER_EVENTS,
    GuaranteeIssuerAdapterError,
    GuaranteeIssuerAdapterRegistry,
    GuaranteeIssuerCapabilityManifest,
    GuaranteeIssuerInboundRequest,
    GuaranteeIssuerOperationResult,
    GuaranteeIssuerOutboundCommand,
    GuaranteeIssuerProviderState,
    GuaranteeIssuerReconciliationGuarantee,
    GuaranteeIssuerReconciliationScope,
    GuaranteeIssuerReconciliationSnapshot,
    GuaranteeIssuerStateQuery,
    NormalizedGuaranteeIssuerEvent,
    TranslatedGuaranteeIssuerError,
)


def _manifest(**overrides):
    data = {
        "integration_modes": frozenset({"WEBHOOK_CALLBACK", "POLLING"}),
        "supported_commands": frozenset({"ISSUE_GUARANTEE", "QUERY_GUARANTEE_STATE"}),
        "supported_inbound_events": CANONICAL_GUARANTEE_ISSUER_EVENTS,
        "authentication_method": "TEST_SIGNATURE",
        "supports_polling": True,
        "supports_webhook": True,
        "supports_reconciliation_snapshot": True,
        "supports_idempotency_key": True,
        "supports_event_sequence": True,
        "rate_limit_policy_reference": "test-only",
        "provider_contract_version": "issuer-test-v1",
        "adapter_mapping_version": "issuer-map-v1",
        "inbound_normalization_version": "issuer-normalize-v1",
        "outbound_mapping_version": "issuer-outbound-v1",
    }
    data.update(overrides)
    return GuaranteeIssuerCapabilityManifest(**data)


def _event(**overrides):
    data = {
        "provider_id": uuid4(),
        "external_event_id": "issuer-event-1",
        "event_type": "GUARANTEE_ISSUED",
        "schema_version": 1,
        "external_guarantee_id": "guarantee-1",
        "issued_amount": "100.000000000000000001",
        "beneficiary_lender_reference": "lender-1",
        "issue_date": datetime.now(UTC),
        "provider_state": "ISSUED",
        "event_time": datetime.now(UTC),
        "received_at": datetime.now(UTC),
        "evidence_references": ["evidence:issuer:1"],
        "payload_hash": "a" * 64,
        "provider_contract_version": "issuer-test-v1",
        "adapter_mapping_version": "issuer-map-v1",
        "inbound_normalization_version": "issuer-normalize-v1",
    }
    data.update(overrides)
    return NormalizedGuaranteeIssuerEvent(**data)


def _reconciliation_guarantee(**overrides):
    data = {
        "external_guarantee_id": "guarantee-1",
        "issued_amount": "100",
        "beneficiary_lender_reference": "lender-1",
        "issue_date": datetime.now(UTC),
        "provider_state": "ISSUED",
        "observed_at": datetime.now(UTC),
        "evidence_references": ["evidence:issuer:row:1"],
    }
    data.update(overrides)
    return GuaranteeIssuerReconciliationGuarantee(**data)


def test_manifest_accepts_only_canonical_guarantee_issuer_events() -> None:
    manifest = _manifest()
    assert manifest.supported_inbound_events == CANONICAL_GUARANTEE_ISSUER_EVENTS

    with pytest.raises(ValidationError):
        _manifest(
            supported_inbound_events=frozenset(
                {*CANONICAL_GUARANTEE_ISSUER_EVENTS, "PROVIDER_SPECIFIC_STATUS"}
            )
        )


def test_normalized_issuer_event_uses_exact_decimal_and_authoritative_evidence() -> None:
    event = _event()
    assert str(event.issued_amount_decimal()) == "100.000000000000000001"

    with pytest.raises(ValidationError):
        _event(issued_amount="0")

    with pytest.raises(ValidationError):
        _event(issued_amount="100.0000000000000000001")

    with pytest.raises(ValidationError):
        _event(evidence_references=[])

    with pytest.raises(ValidationError):
        _event(evidence_references=[""])


def test_issuer_event_requires_timezone_aware_timestamps() -> None:
    naive = datetime.now().replace(tzinfo=None)

    with pytest.raises(ValidationError):
        _event(issue_date=naive)

    with pytest.raises(ValidationError):
        _event(event_time=naive)

    with pytest.raises(ValidationError):
        _event(received_at=naive)


def test_claim_events_require_applicable_authoritative_references() -> None:
    acknowledged = _event(
        event_type="CLAIM_ACKNOWLEDGED",
        claim_reference="claim-1",
    )
    assert acknowledged.claim_reference == "claim-1"

    with pytest.raises(ValidationError):
        _event(event_type="CLAIM_ACKNOWLEDGED")

    settled = _event(
        event_type="CLAIM_SETTLEMENT_CONFIRMED",
        claim_reference="claim-1",
        settlement_reference="settlement-1",
    )
    assert settled.settlement_reference == "settlement-1"

    with pytest.raises(ValidationError):
        _event(
            event_type="CLAIM_SETTLEMENT_CONFIRMED",
            claim_reference="claim-1",
        )


def test_reconciliation_snapshot_requires_authoritative_source_and_valid_rows() -> None:
    provider_id = uuid4()
    snapshot = GuaranteeIssuerReconciliationSnapshot(
        provider_id=provider_id,
        snapshot_at=datetime.now(UTC),
        source_reference="issuer-statement-1",
        evidence_references=[],
        guarantees=[_reconciliation_guarantee()],
    )
    assert snapshot.provider_id == provider_id
    assert len(snapshot.guarantees) == 1

    with pytest.raises(ValidationError):
        GuaranteeIssuerReconciliationSnapshot(
            provider_id=provider_id,
            snapshot_at=datetime.now(UTC),
            source_reference=None,
            evidence_references=[],
            guarantees=[],
        )

    with pytest.raises(ValidationError):
        _reconciliation_guarantee(issued_amount="0")


class StubGuaranteeIssuerAdapter:
    def __init__(self, provider_id):
        self.provider_id = provider_id

    def capability_manifest(self):
        return _manifest()

    async def submit_command(
        self,
        command: GuaranteeIssuerOutboundCommand,
    ) -> GuaranteeIssuerOperationResult:
        assert command.provider_id == self.provider_id
        return GuaranteeIssuerOperationResult(state="ACKNOWLEDGED")

    async def fetch_state(
        self,
        query: GuaranteeIssuerStateQuery,
    ) -> GuaranteeIssuerProviderState:
        return GuaranteeIssuerProviderState(
            provider_id=query.provider_id,
            external_guarantee_id=query.external_guarantee_id,
            provider_state="ISSUED",
            observed_at=datetime.now(UTC),
            evidence_references=["evidence:issuer:state"],
        )

    async def fetch_reconciliation_snapshot(
        self,
        scope: GuaranteeIssuerReconciliationScope,
    ) -> GuaranteeIssuerReconciliationSnapshot:
        return GuaranteeIssuerReconciliationSnapshot(
            provider_id=scope.provider_id,
            snapshot_at=datetime.now(UTC),
            source_reference="issuer-statement-1",
            evidence_references=["evidence:issuer:snapshot"],
            guarantees=[_reconciliation_guarantee()],
        )

    async def verify_and_normalize(
        self,
        request: GuaranteeIssuerInboundRequest,
    ) -> NormalizedGuaranteeIssuerEvent:
        if request.headers.get("x-test-signature") != "valid":
            raise GuaranteeIssuerAdapterError(
                "PROVIDER_AUTHENTICATION_FAILED",
                "test signature rejected",
            )
        return _event(provider_id=request.provider_id)

    def translate_error(self, error: Exception) -> TranslatedGuaranteeIssuerError:
        return TranslatedGuaranteeIssuerError(
            code="PROVIDER_OUTCOME_UNKNOWN",
            classification="UNKNOWN_OUTCOME",
        )

    async def health_check(self):
        return "AVAILABLE"


@pytest.mark.asyncio
async def test_registry_is_provider_scoped_and_adapter_contract_preserves_unknown_outcome() -> None:
    provider_id = uuid4()
    other_provider_id = uuid4()
    adapter = StubGuaranteeIssuerAdapter(provider_id)
    registry = GuaranteeIssuerAdapterRegistry()
    registry.register(provider_id, adapter)

    assert registry.resolve(provider_id) is adapter

    with pytest.raises(GuaranteeIssuerAdapterError) as missing:
        registry.resolve(other_provider_id)
    assert missing.value.code == "GUARANTEE_ISSUER_ADAPTER_NOT_CONFIGURED"

    request = GuaranteeIssuerInboundRequest(
        provider_id=provider_id,
        body=b"{}",
        headers={"x-test-signature": "valid"},
        received_at=datetime.now(UTC),
        correlation_id=uuid4(),
    )
    normalized = await adapter.verify_and_normalize(request)
    assert normalized.provider_id == provider_id

    translated = adapter.translate_error(TimeoutError())
    assert translated.code == "PROVIDER_OUTCOME_UNKNOWN"
    assert translated.classification == "UNKNOWN_OUTCOME"
