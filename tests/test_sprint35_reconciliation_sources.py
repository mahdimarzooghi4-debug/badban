from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from badban.application.idempotency import canonical_request_hash
from badban.application.reconciliation_sources import (
    SNAPSHOT_ADAPTER,
    CustodyRecord,
    CustodySnapshot,
    IssuerRecord,
    IssuerSnapshot,
    LedgerRecord,
    LedgerSnapshot,
    ReconciliationSourceRegistry,
    ReconciliationSourceUnavailable,
    RegistryRecord,
    RegistrySnapshot,
    SettlementRecord,
    SettlementSnapshot,
    SourceCapability,
    SourceTarget,
    SourceType,
    canonical_fields,
    stable_key,
    verify_source_snapshot,
)

NOW = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)
SOURCE_ID = UUID("00000000-0000-0000-0000-000000000031")
SCOPE = {"program": "pilot-1"}


def _target(kind: str) -> SourceTarget:
    if kind == "LEDGER":
        return SourceTarget(reconciliation_type=cast(SourceType, kind), program_id=SOURCE_ID)
    if kind == "LENDER":
        return SourceTarget(reconciliation_type=cast(SourceType, kind), provider_id=SOURCE_ID)
    return SourceTarget(
        reconciliation_type=cast(SourceType, kind), source_legal_entity_id=SOURCE_ID
    )


def _record(kind: str):
    if kind == "GUARANTEE_ISSUER":
        return IssuerRecord(
            observed_at=NOW,
            external_guarantee_id="guarantee-1",
            issued_amount="100.00",
            issued_at=NOW,
            beneficiary=uuid4(),
            state="ISSUED",
            currency="IRR",
        )
    if kind == "CUSTODY":
        return CustodyRecord(
            observed_at=NOW,
            asset_position_id=uuid4(),
            custody_reference="receipt-1",
            asset_type="CONFIGURED_ASSET",
            quantity="2.500",
            unit_code="GRAM",
            state="RESTRICTED",
            ownership_reference="document-1",
            control_reference="control-1",
        )
    if kind == "SETTLEMENT":
        return SettlementRecord(
            observed_at=NOW,
            settlement_reference="settlement-1",
            amount="2500",
            currency="IRR",
            payer_role="ISSUER",
            payee_role="LENDER",
            value_date=NOW,
            state="OBSERVED",
        )
    if kind == "COLLATERAL_REGISTRY":
        return RegistryRecord(
            observed_at=NOW,
            registration_id="registry-1",
            state="REGISTERED",
            collateral_reference="collateral-1",
            secured_amount="100",
        )
    return LedgerRecord(
        observed_at=NOW,
        account_code="1000",
        currency="IRR",
        economic_owner_type="PROGRAM",
        economic_owner_id=None,
        participant_id=None,
        program_id=SOURCE_ID,
        provider_id=None,
        asset_position_id=None,
        guarantee_case_id=None,
        claim_id=None,
        reserve_account_id=None,
        ledger_layer="MEMORANDUM_CONTROL",
        normal_balance="DEBIT",
        balance="10.5",
    )


_CLASSES = {
    "GUARANTEE_ISSUER": IssuerSnapshot,
    "CUSTODY": CustodySnapshot,
    "SETTLEMENT": SettlementSnapshot,
    "COLLATERAL_REGISTRY": RegistrySnapshot,
    "LEDGER": LedgerSnapshot,
}


def _snapshot(kind: str, *, records=None):
    cls = _CLASSES[kind]
    supplied = [_record(kind)] if records is None else records
    draft = cls.model_construct(
        source_id=SOURCE_ID,
        scope_definition=SCOPE,
        snapshot_at=NOW,
        received_at=NOW + timedelta(minutes=1),
        source_reference="provider-audit-1",
        schema_version="reconciliation-source-v1",
        contract_version="provider-1",
        mapping_version="mapping-1",
        normalization_version=None,
        evidence_references=("evidence-1",),
        coverage_from=NOW - timedelta(days=1),
        coverage_to=NOW,
        watermark="cursor-1",
        content_hash="0" * 64,
        reconciliation_type=cast(SourceType, kind),
        records=tuple(supplied),
    )
    data = draft.model_dump(mode="json")
    data["content_hash"] = canonical_request_hash(draft.semantic_payload())
    return SNAPSHOT_ADAPTER.validate_python(data)


def _capability(kind: str) -> SourceCapability:
    return SourceCapability(
        source_id=SOURCE_ID,
        reconciliation_type=cast(SourceType, kind),
        contract_version="provider-1",
        mapping_version="mapping-1",
    )


@pytest.mark.parametrize("kind", list(_CLASSES))
def test_five_source_contracts_verify_provenance_and_stable_identity(kind):
    target = _target(kind)
    snapshot = _snapshot(kind)
    assert (
        verify_source_snapshot(
            target=target, scope=SCOPE, capability=_capability(kind), snapshot=snapshot
        )
        == snapshot
    )
    assert stable_key(snapshot.records[0])
    assert canonical_fields(snapshot.records[0])


@pytest.mark.parametrize("kind", list(_CLASSES))
def test_source_identity_shape_rejects_wrong_or_ambiguous_ownership(kind):
    with pytest.raises(ValidationError):
        SourceTarget(reconciliation_type=cast(SourceType, kind), provider_id=SOURCE_ID)
    with pytest.raises(ValidationError):
        SourceTarget(
            reconciliation_type=cast(SourceType, kind),
            program_id=SOURCE_ID,
            source_legal_entity_id=SOURCE_ID,
        )


@pytest.mark.parametrize("kind", list(_CLASSES))
@pytest.mark.parametrize(
    "mutation", ["hash", "source", "scope", "schema", "future", "missing_evidence"]
)
def test_tampered_source_snapshots_fail_validation(kind, mutation):
    data = _snapshot(kind).model_dump(mode="json")
    if mutation == "hash":
        data["records"][0]["state" if kind != "LEDGER" else "balance"] = "ALTERED"
    elif mutation == "source":
        data["source_id"] = str(uuid4())
    elif mutation == "scope":
        data["scope_definition"] = {"program": "other"}
    elif mutation == "schema":
        data["schema_version"] = "unsupported-source-schema"
    elif mutation == "future":
        data["coverage_to"] = (NOW + timedelta(days=3)).isoformat()
    else:
        data["evidence_references"] = []
    if mutation == "hash":
        with pytest.raises(ValidationError):
            SNAPSHOT_ADAPTER.validate_python(data)
        return
    if mutation in {"schema", "future", "missing_evidence"}:
        with pytest.raises(ValidationError):
            SNAPSHOT_ADAPTER.validate_python(data)
        return
    # Valid new hash still cannot authorize a different source or target scope.
    data["content_hash"] = canonical_request_hash(
        {k: v for k, v in data.items() if k not in {"received_at", "content_hash"}}
    )
    parsed = SNAPSHOT_ADAPTER.validate_python(data)
    with pytest.raises(ValueError):
        verify_source_snapshot(
            target=_target(kind),
            scope=SCOPE,
            capability=_capability(kind),
            snapshot=parsed,
        )


@pytest.mark.parametrize("kind", list(_CLASSES))
@pytest.mark.parametrize(
    "field,value",
    [
        ("contract_version", "unexpected"),
        ("mapping_version", "untrusted"),
        ("schema_version", "reconciliation-source-v2"),
        ("normalization_version", "unapproved"),
    ],
)
def test_source_capability_version_mismatch_fails_closed(kind, field, value):
    cap = _capability(kind)
    replacement = {**cap.__dict__, field: value}
    with pytest.raises(ValueError):
        verify_source_snapshot(
            target=_target(kind),
            scope=SCOPE,
            capability=SourceCapability(**replacement),
            snapshot=_snapshot(kind),
        )


def test_changed_source_type_or_future_record_observation_is_rejected():
    original = _snapshot("GUARANTEE_ISSUER")
    with pytest.raises(ValueError):
        verify_source_snapshot(
            target=_target("CUSTODY"),
            scope=SCOPE,
            capability=_capability("CUSTODY"),
            snapshot=original,
        )
    delayed = _record("GUARANTEE_ISSUER").model_copy(
        update={"observed_at": NOW + timedelta(hours=3)}
    )
    with pytest.raises(ValueError, match="observation"):
        verify_source_snapshot(
            target=_target("GUARANTEE_ISSUER"),
            scope=SCOPE,
            capability=_capability("GUARANTEE_ISSUER"),
            snapshot=_snapshot("GUARANTEE_ISSUER", records=[delayed]),
        )


def test_receipt_timestamp_is_not_semantic_source_identity():
    snapshot = _snapshot("SETTLEMENT")
    data = snapshot.model_dump(mode="json")
    data["received_at"] = (NOW + timedelta(minutes=3)).isoformat()
    updated = SNAPSHOT_ADAPTER.validate_python(data)
    assert updated.content_hash == snapshot.content_hash


def test_negative_or_malformed_monetary_values_and_extra_fields_rejected():
    with pytest.raises(ValidationError):
        SettlementRecord(
            observed_at=NOW,
            settlement_reference="s",
            amount="-5",
            currency="IRR",
            payer_role="A",
            payee_role="B",
            value_date=NOW,
            state="PAID",
        )
    data = _snapshot("CUSTODY").model_dump(mode="json")
    data["records"][0]["unapproved_legal_field"] = "fake"
    with pytest.raises(ValidationError):
        SNAPSHOT_ADAPTER.validate_python(data)


class _Port:
    def __init__(self, cap: SourceCapability):
        self._cap = cap

    def capability(self) -> SourceCapability:
        return self._cap

    async def fetch_reconciliation_snapshot(self, target, scope):
        return _snapshot(target.reconciliation_type)


def test_registry_is_explicit_and_fails_closed_on_missing_or_duplicate_port():
    registry = ReconciliationSourceRegistry()
    with pytest.raises(ReconciliationSourceUnavailable) as exc:
        registry.resolve(_target("CUSTODY"))
    assert exc.value.code == "SOURCE_UNAVAILABLE"
    port = _Port(_capability("CUSTODY"))
    registry.register(port)
    assert registry.resolve(_target("CUSTODY")) is port
    with pytest.raises(ValueError, match="already registered"):
        registry.register(port)
    with pytest.raises(ReconciliationSourceUnavailable):
        registry.resolve(_target("SETTLEMENT"))
